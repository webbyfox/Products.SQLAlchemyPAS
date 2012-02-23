from AccessControl.Permissions import add_user_folders
from Products.PluggableAuthService.PluggableAuthService import registerMultiPlugin
from Products.SQLAlchemyPAS import plugin




def initialize(context):
    registerMultiPlugin(plugin.SQLAlchemyPASPlugin.meta_type)
    
    context.registerClass(plugin.SQLAlchemyPASPlugin,
            permission = add_user_folders,
            constructors = (plugin.manage_addSQLAlchemyPASPluginForm,
                            plugin.manage_addSQLAlchemyPASPlugin),
            visibility = None)
