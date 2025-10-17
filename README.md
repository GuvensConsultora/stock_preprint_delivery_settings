# stock_preprinted_delivery_settings (Odoo 17)

Bloque de ajustes en **Inventario** para configurar la *cantidad de líneas* impresas en **remitos/albaranes preimpresos** por tipo de operación (**OUT** e **INT**).

## Instalación
1. Copiar este módulo a la ruta de addons (por ejemplo, `/mnt/extra-addons`).
2. Actualizar la lista de apps y **instalar** *stock_preprinted_delivery_settings*.

## Uso
- Ir a **Inventario → Configuración → Ajustes**.
- Bloque **Albaranes preimpresos**:
  - *Líneas por albarán (OUT)*
  - *Líneas por albarán (INT)*

Los valores se guardan en `ir.config_parameter`:
- `stock_preprinted_delivery.preprint_lines_out`
- `stock_preprinted_delivery.preprint_lines_int`

### Lectura de parámetros (ejemplo)
```python
lines_out = int(env['ir.config_parameter'].sudo().get_param(
    "stock_preprinted_delivery.preprint_lines_out", default="25"
))
lines_int = int(env['ir.config_parameter'].sudo().get_param(
    "stock_preprinted_delivery.preprint_lines_int", default="25"
))
```

## Estructura
```
stock_preprinted_delivery_settings/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── res_config_settings.py
├── views/
│   └── res_config_settings_views.xml
└── README.md
```

## Notas
- Probado en **Odoo 17**. Si tu paquete de `stock` altera la vista de ajustes, habilitá la *variante alternativa* comentada al final del XML.
- Este módulo **no** modifica reportes; solo expone parámetros para que otros módulos/reportes los consuman.
