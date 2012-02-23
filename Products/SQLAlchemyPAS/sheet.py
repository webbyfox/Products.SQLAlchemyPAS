from zope.interface import implements
from Products.PlonePAS.interfaces.propertysheets import IMutablePropertySheet
from sqlalchemy import orm, types
import datetime
from DateTime import DateTime

_SQL_PROPERTY_TYPE = {
    types.Boolean:  'boolean',
    types.DateTime: 'date',
    types.Integer:  'int',
    types.Float:    'float',
    types.Text:     'text', # watch the order here
    types.String:   'string',
    } # omitted long, lines, selection, multiple selection

def map_type(sqltype):
    """ Map a SQLAlchemy column type to PropertyManager property type
    """
    for k, v in _SQL_PROPERTY_TYPE.items():
        if isinstance(sqltype, k):
            return v

def cast_date(x):
    return x.asdatetime()

_PROPERTY_CASTS = {
    'boolean': bool,
    'int': int,
    'float': float,
    'text': unicode,
    'string': unicode,
    'date': lambda x: x.asdatetime(),
    }

def cast_value(property_type, value):
    """ Cast a property value to its type
    """
    if value is None:
        return None
    cast = _PROPERTY_CASTS.get(property_type, None)
    if cast is None:
        return value
    return cast(value)


class SAMutablePropertySheet(object):
    implements(IMutablePropertySheet)

    def __init__(self, user, plugin):
        self.user = user
        self.plugin = plugin
    
    @property
    def table(self):
        return orm.object_mapper(self.user).local_table

    #
    # IPropertySheet
    #
    
    def getId(self):
        """ Identify the sheet within a collection.
        """
        return self.plugin.getId()

    def hasProperty(self, id):
        """ Does the sheet have a property corresponding to 'id'?
        """
        return self.table.columns.has_key(id)

    def getProperty(self, id, default=None):
        """ Return the value of the property corresponding to 'id'.

        o If no such property exists within the sheet, return 'default'.
        """
        value = getattr(self.user, id, default)
        if isinstance(value, datetime.datetime):
            value = DateTime(value)
        return value

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

    def setProperty(self, obj, id, value):
        """ obj is the IPropertiedUser
        """
        property_type = self.getPropertyType(id)
        value = cast_value(property_type, value)
        setattr(self.user, id, value)

    def setProperties(self, obj, mapping):
        """ obj is the IPropertiedUser
        """
        for id, value in mapping.items():
            self.setProperty(obj, id, value)


