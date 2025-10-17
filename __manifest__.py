{
    "name": "stock_preprinted_delivery_settings",
    "version": "17.0.1.0.0",
    "summary": "Bloque de ajustes para remitos/albaranes preimpresos (OUT/INT)",
    "category": "Inventory/Configuration",
    "author": "Tu Organización",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": ["stock","operating_unit","stock_operating_unit"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_type_views.xml",
        "views/res_config_settings_views.xml",
        "views/hello_wizard_views.xml",
        "views/stock_picking_replace_print.xml",
    ],
    "post_init_hook": "post_init_set_print_sequences_on_types",     # Función que voy a llamar
    "assets": {},
    "installable": True,
    "application": False
}
