#XXX umm, I think this whole file is not used

from z3c.saconfig.scopedsession import named_scoped_session
from sqlalchemy import Table, MetaData, orm, types
#from Products.PluggableAuthService.interfaces.propertysheets import IPropertySheet
from Products.PlonePAS.interfaces.propertysheets import IMutablePropertySheet
from zope.interface import implements

Session = named_scoped_session('users')
metadata = MetaData()

TABLENAME = 'plone_users'
ID_COLUMN = LOGIN_COLUMN = 'username'
PASSWORD_COLUMN = 'password'


_SQL_PROPERTY_TYPE = {
    types.Boolean:  'boolean',
    types.DateTime: 'date',
    types.Integer:  'int',
    types.Float:    'float',
    types.Text:     'text', # watch the order here
    types.String:   'string',
    } # omitted long, lines, selection, multiple selection

_PROPERTY_CASTS = {
    'boolean': bool,
    'int': int,
    'float': float,
    'text': unicode,
    'string': unicode,
    }

def map_type(sqltype):
    for k, v in _SQL_PROPERTY_TYPE.items():
        if isinstance(sqltype, k):
            return v

def fix_type(property_type, value):
    if value is None:
        return None
    cast = _PROPERTY_CASTS.get(property_type, None)
    if cast is None:
        return value
    return cast(value)

class User(object):
    implements(IMutablePropertySheet)

    @property
    def table(self):
        return orm.object_session(self).query(self.__class__).table

    def setPropertySheetId(self, id):
        """ Set the id of the sheet within the collection.
        """
        self._sheet_id = id

    #
    # IPropertySheet
    #
    
    def getId(self):
        """ Identify the sheet within a collection.
        """
        return self._sheet_id

    def hasProperty(self, id):
        """ Does the sheet have a property corresponding to 'id'?
        """
        return self.table.columns.has_key(id)

    def getProperty(self, id, default=None):
        """ Return the value of the property corresponding to 'id'.

        o If no such property exists within the sheet, return 'default'.
        """
        return getattr(self, id, default)

    def getPropertyType(self, id):
        """ Return the string identifying the type of property, 'id'.

        o If no such property exists within the sheet, return None.
        """
        column = self.table.columns.get(id, None)
        if column is not None:
            return map_type(column.type)

    def propertyInfo(self, id):
        """ Return a mapping describing property, 'id'.

        o Keys must include:

          'id'  -- the unique identifier of the property.

          'type' -- the string identifying the property type.

          'meta' -- a mapping containing additional info about the property.
        """
        return dict(id=id, type=self.getPropertyType(id), meta={})

    def propertyMap(self):
        """ Return a tuple of 'propertyInfo' mappings, one per property.
        """
        return tuple(self.propertyInfo(id) for id in self.propertyIds())

    def propertyIds(self):
        """ Return a sequence of the IDs of the sheet's properties.
        """
        return self.table.columns.keys()

    def propertyValues(self):
        """ Return a sequence of the values of the sheet's properties.
        """
        return [self.getProperty(id) for id in self.propertyIds()]

    def propertyItems(self):
        """ Return a sequence of ( id, value ) tuples, one per property.
        """
        return [(id, self.getProperty(id)) for id in self.propertyIds()]

    #
    # IMutablePropertySheet
    #
    
    def canWriteProperty(self, user, id):
        """ Check if a property can be modified.
        """
        return True

    def setProperty(self, user, id, value):
        """
        """
        property_type = self.getPropertyType(id)
        value = fix_type(property_type, value)
        setattr(self, id, value)

    def setProperties(self, user, mapping):
        """
        """
        for id, value in mapping.items():
            self.setProperty(user, id, value)
    

users_table = Table(TABLENAME, metadata, autoload=True, autoload_with=Session().bind)
orm.Mapper(User, users_table)



