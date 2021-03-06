import torndb
import time
import os
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options
from binascii import hexlify

define("port", default=1104, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="database host")
define("mysql_database", default="ticketing", help="database name")
define("mysql_user", default="tick", help="database user")
define("mysql_password", default="tick", help="database password")


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/login", Login),
            (r"/signup", Signup),
            (r"/logout", Logout),
            (r"/sendticket", SendTicket),
            (r"/getticketcli", GetTicketCli),
            (r"/closeticket", CloseTicket),
            (r"/getticketmod", GetTicketMod),
            (r"/restoticketmod", ResToTicketMod),
            (r"/changestatus", ChangeStatus),
            (r".*", DefaultHandler),

        ]
        settings = dict()
        super(Application, self).__init__(handlers, **settings)
        self.db = torndb.Connection(
            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db


class DefaultHandler(BaseHandler):
    def get(self):
        pass


class Signup(BaseHandler):
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        firstname = self.get_argument('firstname', None)
        lastname = self.get_argument('lastname', None)
        type = self.get_argument('type')

        if not username or not password or not type:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        if not (type == 'a' or type == 'c'):
            msg = {'message': 'Invalid input',
                   'code': '403'}
            self.write(msg)
            return

        users = self.db.query("SELECT * FROM users WHERE username=%s", username)
        if len(users) > 0:
            msg = {'message': 'Username already exists!'
                   , 'code': '201'}
            self.write(msg)
            return

        self.db.execute("INSERT INTO users (username, password, firstname, lastname, type) "
                        "VALUES (%s,%s,%s,%s,%s) ", username , password, firstname, lastname, type)

        msg = {'message': 'Signed Up Successfully',
               'code': '200'}

        self.write(msg)


class Login(BaseHandler):
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')

        if not username or not password:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        response = self.db.get("SELECT token, type FROM users WHERE username=%s AND password=%s",
                               username, password)

        if response:
            if response.token:
                msg = {'message': 'Already logged in!',
                       'code': '202',
                       'token': response.token,
                       'type': response.type}
                self.write(msg)
                return

            token = str(hexlify(os.urandom(16)))
            self.db.execute("UPDATE users SET token=%s WHERE username=%s AND password=%s ",
                            token, username, password)

            msg = {'message': 'Logged in Successfully!',
                   'code': '200',
                   'token': token,
                   'type': response.type}
            self.write(msg)
            return

        else:
            msg = {'message': 'Wrong username/password pair!',
                   'code': '203'}
            self.write(msg)
            return



class Logout(BaseHandler):
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')

        if not username or not password:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        response = self.db.get("SELECT * FROM users WHERE username=%s AND password=%s",
                               username, password)

        if response:
            token = self.db.get("SELECT token FROM users WHERE username=%s AND password=%s",
                                username, password)

            if token['token']:
                self.db.execute("UPDATE users SET token=NULL WHERE username=%s AND password=%s ",
                                 username, password)
                msg = {'message': 'Logged Out Successfully!',
                       'code': '200'}

                self.write(msg)
            else:
                msg = {'message': 'Already Logged out!',
                       'code': '204'}
                self.write(msg)
        else:
            msg = {'message': 'User doesn\'t exists!',
                   'code': '205'}
            self.write(msg)


class SendTicket(BaseHandler):
    def post(self):
        token = self.get_argument('token')
        subject = self.get_argument('subject')
        body = self.get_argument('body')

        if not subject or not body:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        user = self.db.get("SELECT user_id, token FROM users WHERE token=%s", token)

        user_id = user.user_id
        user_id = int(user_id)
        if user.token:
            print(user.user_id)
            self.db.execute("INSERT INTO tickets (user_id, subject, body, response, status, date)"
                            "VALUES (%s,%s,%s,%s,'Open', %s)", user_id, subject, body, None,
                            time.strftime('%Y-%m-%d %H:%M:%S'))

            ticket_id = self.db.execute("SELECT LAST_INSERT_ID()")
            msg = {'message': 'Ticket Sent Successfully!',
                   'id': ticket_id,
                   'code': '200'}

            self.write(msg)

        else:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)

            return


class GetTicketCli(BaseHandler):
    def post(self):
        token = self.get_argument('token')
        user = self.db.get("SELECT user_id, type FROM users WHERE token=%s", token)

        if not user:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)
            return

        if user.type == 'a':
            msg = {'message': 'Admins not allowed to perform this method!',
                   'code': '301'}
            self.write(msg)
            return

        user_id = user.user_id
        tickets = self.db.query("SELECT * FROM tickets WHERE user_id=%s", user_id)

        msg = {'tickets': 'There is(are) -'+str(len(tickets))+'- Ticket(s)',
               'code': '200'}

        for i in range(0, len(tickets)):
            if not tickets[i].response:
                entry = {'subject': tickets[i].subject,
                         'body': tickets[i].body,
                         'status': tickets[i].status,
                        'id': tickets[i].ticket_id,
                        'date': str(tickets[i].date)}
            else:
                entry = {'subject': tickets[i].subject,
                         'body': tickets[i].body,
                         'response': tickets[i].response,
                         'status': tickets[i].status,
                         'id': tickets[i].ticket_id,
                         'date': str(tickets[i].date)}

            msg['block '+str(i)] = entry

        self.write(msg)



class CloseTicket(BaseHandler):
    def post(self):
        token = self.get_argument('token')
        ticket_id = self.get_argument('id')

        if not ticket_id:
            msg = {'message': 'Invalid input!',
                   'cdoe': '403'}
            self.write(msg)
            return

        user = self.db.get("SELECT * FROM users WHERE token=%s", token)

        if not user:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)
            return

        if user.type == 'a':
            msg = {'message': 'Admins are not allowed to perform this method!',
                   'code': '301'}
            self.write(msg)
            return

        ticket = self.db.get("SELECT * FROM tickets WHERE ticket_id=%s", ticket_id)

        if not ticket:
            msg = {'message': 'Invalid ticket id!',
                   'code': '400'}
            self.write(msg)
            return

        if ticket.user_id != user.user_id:
            msg = {'message': 'Ticket belongs to another user, you can\'t change it!',
                   'code': '401'}
            self.write(msg)
            return
        self.db.execute("UPDATE tickets SET status='Closed' WHERE ticket_id=%s", ticket_id)

        msg = {'message': 'Ticket With id -' + str(ticket_id) + '- Closed Successfully!',
               'code': '200'}
        self.write(msg)
        return


class GetTicketMod(BaseHandler):
    def post(self):
        token = self.get_argument('token')

        user = self.db.get("SELECT type FROM users WHERE token=%s", token)

        if not user:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)
            return

        if user.type != 'a':
            msg = {'message': 'Users are not allowed to perfrom this method!',
                   'code': '302'}
            self.write(msg)
            return

        tickets = self.db.query("SELECT * FROM tickets")

        msg = {'tickets': 'There is(are) -' + str(len(tickets)) + '- Ticket(s)',
               'code': '200'}

        for i in range(0, len(tickets)):
            if not tickets[i].response:
                entry = {'subject': tickets[i].subject,
                         'body': tickets[i].body,
                         'status': tickets[i].status,
                         'id': tickets[i].ticket_id,
                         'date': str(tickets[i].date)}
            else:
                entry = {'subject': tickets[i].subject,
                         'body': tickets[i].body,
                         'response': tickets[i].response,
                         'status': tickets[i].status,
                         'id': tickets[i].ticket_id,
                         'date': str(tickets[i].date)}

            msg['block ' + str(i)] = entry

        self.write(msg)


class ResToTicketMod(BaseHandler):
    def post(self):
        token = self.get_argument('token')
        ticket_id = self.get_argument('id')
        body = self.get_argument('body')

        if not ticket_id or not body:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        user = self.db.get("SELECT type FROM users WHERE token=%s", token)

        if not user:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)
            return

        if user.type != 'a':
            msg = {'message': 'Users are not allowed to perform this method!',
                   'code': '302'}
            self.write(msg)
            return

        ticket = self.db.get("SELECT * FROM tickets WHERE ticket_id=%s", ticket_id)

        if not ticket:
            msg = {'message': 'Invalid ticket id!',
                   'code': '400'}
            self.write(msg)
            return

        self.db.execute("UPDATE tickets SET response=%s, status=%s WHERE ticket_id=%s", body, "Closed", ticket_id)

        msg = {'message': 'Response to Ticket With id -' + str(ticket_id) + '- Sent Successfully',
               'code': '200'}

        self.write(msg)


class ChangeStatus(BaseHandler):
    def post(self):
        token = self.get_argument('token')
        ticket_id = self.get_argument('id')
        status = self.get_argument('status')

        if not ticket_id or not status:
            msg = {'message': 'Invalid input!',
                   'code': '403'}
            self.write(msg)
            return

        user = self.db.get("SELECT type FROM users WHERE token=%s", token)

        if not user:
            msg = {'message': 'Invalid token!',
                   'code': '300'}
            self.write(msg)
            return

        if user.type != 'a':
            msg = {'message': 'Users are not allowed to perform this method!',
                   'code': '302'}
            self.write(msg)
            return

        ticket = self.db.get("SELECT * FROM tickets WHERE ticket_id=%s", ticket_id)

        if not ticket:
            msg = {'message': 'Invalid ticket id!',
                   'code': '400'}
            self.write(msg)
            return

        if not (status.lower() == 'open' or status.lower() == 'closed' or
                status.lower() == 'in progress'):
            msg = {'message': 'Invalid status only \'Closed\' \'Open\' and \'In Progress\' Are Allowd',
                   'code': '402'}
            self.write(msg)
            return

        self.db.execute("UPDATE tickets SET status=%s WHERE ticket_id=%s", status.title(), ticket_id)
        msg = {'message': 'Status Ticket With id -' + str(ticket_id) + '- Changed Successfully',
               'code': '200'}
        self.write(msg)


def main():
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


main()
