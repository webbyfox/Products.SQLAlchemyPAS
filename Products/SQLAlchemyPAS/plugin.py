import threading
import datetime
import DateTime

from zope.interface import implements
from zope import component
from sqlalchemy import orm, sql, Table, MetaData
from sqlalchemy.exceptions import SQLAlchemyError

try:
    # >= Plone 4
    from zope.component import ComponentLookupError
except ImportError:
    # deprecated
    from zope.component.exceptions import ComponentLookupError

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.interfaces import plugins as pas
from Products.PlonePAS.interfaces import plugins as plonepas
from Products.PlonePAS.interfaces import capabilities

from sheet import SAMutablePropertySheet
from encryption import IEncryptionPolicy

from z3c.saconfig.interfaces import IScopedSession
from z3c.saconfig.scopedsession import named_scoped_session

manage_addSQLAlchemyPASPluginForm = PageTemplateFile('plugin', globals())

def manage_addSQLAlchemyPASPlugin(dispatcher, id, title=None, REQUEST=None):
    """Add a session plugin."""
    plugin = SQLAlchemyPASPlugin(id, title=title)
    dispatcher._setObject(id, plugin)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect('%s/manage_workspace?'
                                  'manage_tabs_message=Plugin+created.' %
                                  dispatcher.absolute_url())

#
# This is a mapping from (session_name, table_name) -> Mapped class
#
_MODELS = {}
_MODELS_LOCK = threading.Lock()

def get_model(session_name, table_name):
    # optimistically try get without lock
    key = (session_name, table_name)
    model = _MODELS.get(key, None)
    if model is not None:
        return model
    # no model, lock and redo
    session = named_scoped_session(session_name)()
    _MODELS_LOCK.acquire()
    try:
        # need to check, another thread may have got there first
        if key not in _MODELS:

            class Model(object):
                pass

            metadata = MetaData()
            table = Table(table_name, metadata, autoload=True, autoload_with=session.bind)
            orm.Mapper(Model, table)

            _MODELS[key] = Model
        return _MODELS[key]
    finally:
        _MODELS_LOCK.release()

def reset_model(session_name, table_name):
    key = (session_name, table_name)
    _MODELS_LOCK.acquire()
    try:
        if key in _MODELS:
            del _MODELS[key]
    finally:
        _MODELS_LOCK.release()


class SQLAlchemyPASPlugin(BasePlugin):
    implements(
        pas.IAuthenticationPlugin,
        pas.IUserEnumerationPlugin,
        pas.IPropertiesPlugin,
        pas.IUserAdderPlugin,
        pas.ICredentialsUpdatePlugin,
        plonepas.IUserManagement,
        capabilities.IPasswordSetCapability,
        capabilities.IDeleteCapability,
        )

    meta_type = "SQLAlchemy PAS Plugin"

    _properties = (
        {
        "id"    : "title",
        "label" : "Title",
        "type"  : "string",
        "mode"  : "w",
        },
        {
        "id"    : "session_name",
        "label" : "Database session name (registered by a zcml directive)",
        "type"  : "selection",
        "mode"  : "w",
        "select_variable" : "listSessionNames"
        },
        {
        "id"    : "table_name",
        "label" : "Table name",
        "type"  : "string",
        "mode"  : "w",
        },
        {
        "id"    : "login_column",
        "label" : "Login column (must match the user id column to add users)",
        "type"  : "string",
        "mode"  : "w",
        },
        {
        "id"    : "userid_column",
        "label" : "User id column",
        "type"  : "string",
        "mode"  : "w",
        },
        {
        "id"    : "password_column",
        "label" : "Password column",
        "type"  : "string",
        "mode"  : "w",
        },
        {
        "id"    : "password_encryption",
        "label" : "Password encryption method (registered as an utility)",
        "type"  : "selection",
        "mode"  : "w",
        "select_variable" : "listEncryptionPolicies"
        },
        )

    session_name = ''
    table_name = 'users'
    login_column = 'login'
    userid_column = 'userid'
    password_column = 'password'
    password_encryption = 'none'

    def __init__(self, id, title=''):
        self.id = id
        self.title = title


    def _updateProperty(self, id, value):
        super(SQLAlchemyPASPlugin, self)._updateProperty(id, value)
        reset_model(self.session_name, self.table_name)

    def listSessionNames(self):
        return [name for name, util in component.getUtilitiesFor(IScopedSession)]

    @property
    def session(self):
        return named_scoped_session(self.session_name)()

    @property
    def Model(self):
        return get_model(self.session_name, self.table_name)

    @property
    def query(self):
        try:
            return self.session.query(self.Model)
        except (SQLAlchemyError, ComponentLookupError):
            # We want exceptions here (likely ComponentLookupErrors) to be
            # swallowed by PAS
            raise ValueError

    @property
    def table(self):
        try:
            return orm.class_mapper(self.Model).local_table
        except (SQLAlchemyError, ComponentLookupError):
            raise ValueError

    def isPrimaryKey(self, colname):
        return [colname] == self.table.primary_key.columns.keys()

    def hold(self, ob):
        """Delay GC'ing of object for duration of request as SQLAlchemy only
        maintains a weak dict.
        """
        self.REQUEST._hold(ob)

    def encryptPassword(self, password):

        utility = component.getUtility(IEncryptionPolicy, name=self.password_encryption)
        return utility.encryptPassword(password)

    #
    # These methods fulfil the PAS plugin interfaces
    #

    def authenticateCredentials(self, credentials):
        login = credentials['login']
        password = credentials['password']
        user = self._getUserByLogin(login)
        if user is None:
            return None

        if self.encryptPassword(password) == getattr(user, self.password_column).encode('hex'):
            login = getattr(user, self.login_column)
            userid = getattr(user, self.userid_column)
            return userid, login

    def _getUserByLogin(self, login):
        if self.isPrimaryKey(self.login_column):
            # userid column is primary key, lookup cached per request
            user = self.query.get((login,))
            if user is None:
                return None
        else:
            condition = self.table.columns[self.login_column]==login
            results = self.query.filter(condition).limit(2).all()
            if len(results) != 1:
                return None
            user, = results

        self.hold(user)
        return user

    def enumerateUsers(self, id=None, login=None, exact_match=False,
                       sort_by=None, max_results=None, **kw):
        # The swiss army knife of PAS methods

        # acl_users/manage_search passes in '' rather than None
        if id == '':
            id = None
        if login == '':
            login = None

        if isinstance(id, basestring):
            if exact_match and self.isPrimaryKey(self.userid_column):
                info = self._getUserInfo(id)
                return info and (info,) or ()
            else:
                id = [id]

        if isinstance(login, basestring):
            if exact_match and self.isPrimaryKey(self.login_column):
                info = self._getUserInfo(login)
                return info and (info,) or ()
            else:
                login = [login]

        col_values = dict((k, [v]) for k, v in kw.items() if k in self.table.columns)
        if id:
            col_values[self.userid_column] = id
        if login:
            col_values[self.login_column] = login

        if sort_by == 'id':
            sort_by = self.userid_column
        elif sort_by == 'login':
            sort_by = self.login_column

        return self._enumerateUsers(col_values, exact_match, sort_by, max_results)

    def _getUserInfo(self, id):
        """ The common case of enumerateUsers, an exact match to a single value.

        This form may fetch the result from sqlalchemy's session cache
        """
        user = self.query.get((id,))
        if user is not None:
            self.hold(user)
            return dict(id=getattr(user, self.userid_column),
                         login=getattr(user, self.login_column),
                         pluginid=self.getId())

    def _enumerateUsers(self, col_values, exact_match, order_by, max_results):
        """ The extremely generalized case of enumerateUsers

        o col_values is a mapping of column name -> [value, ...]
        o order_by is a column name

        This form always results in database access and the flushing of sqlalchemy's session cache
        """
        query = self.query
        columns = self.table.columns
        criteria = []
        for key, values in col_values.items():
            column = columns[key]
            for value in values:
                if exact_match:
                    criteria.append(column==value)
                else:
                    criteria.append(column.ilike('%'+value+'%'))

        if criteria:
            query = query.filter(sql.or_(*criteria))

        if order_by and order_by in columns:
            query = query.order_by(columns[order_by])

        if max_results:
            query = query.limit(max_results)

        results = query.all()
        self.hold(results)

        pluginid = self.getId()

        return tuple(dict(id=getattr(user, self.userid_column),
                          login=getattr(user, self.login_column),
                          pluginid=pluginid)
                     for user in results
                     )

    def getPropertiesForUser(self, user, request=None):
        # Users that do not come from the database will trigger several
        # database trips per request as there is nothing to cache :-(
        try:
            isPrimaryKey = self.isPrimaryKey(self.userid_column)
            if isPrimaryKey:
                # userid column is primary key, lookup cached per request
                db_user = self.query.get((user.getId(),))
            else:
                column = self.table.columns[self.userid_column]
                results = self.query.filter(column==user.getId()).one()
                if len(results) != 1:
                    return None
                db_user, = results

            if db_user is not None:
                self.hold(db_user)
                return SAMutablePropertySheet(db_user, self)

        except (ValueError, SQLAlchemyError):
            return None # not setup yet

    def doAddUser(self, login, password):
        """ Add a user record to a User Manager, with the given login
            and password

        o Return a Boolean indicating whether a user was added or not
        """
        if self.query.filter_by(**{self.login_column: login}).count():
            return False

        Model = get_model(self.session_name, self.table_name)
        obj = Model()
        setattr(obj, self.login_column, login)
        setattr(obj, self.password_column, self.encryptPassword(password))
        self.session.add(obj)
        return True

    def updateCredentials(self, request, response, login, new_password):
        self.doChangeUser(login, new_password)

    #
    # The PlonePAS methods
    #

    def doChangeUser(self, login, password, **kw):
        """
        Change a user's password (differs from role) roles are set in
        the pas engine api for the same but are set via a role
        manager)
        """
        user = self._getUserByLogin(login)
        enc_pw = self.encryptPassword(password)
        setattr(user, self.password_column, enc_pw)

    def doDeleteUser(self, login):
        """
        Remove a user record from a User Manager, with the given login
        and password

        o Return a Boolean indicating whether a user was removed or
          not
        """
        user = self._getUserByLogin(login)
        if user is None:
            return False
        else:
            self.session.delete(user)
            return True

    def allowDeletePrincipal(self, id):
        """True iff this plugin can delete a certain user/group."""
        return True

    def allowPasswordSet(self, id):
        """True iff this plugin can set the password of a certain user."""
        return True

    def listEncryptionPolicies(self):

        return [n for n, u in component.getUtilitiesFor(IEncryptionPolicy)]