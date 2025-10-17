# hooks.py  (crea secuencias de impresión en tipos OUT/INT al instalar)
# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def post_init_set_print_sequences_on_types(env_or_cr, registry=None):
    """
    Soporta ambas firmas:
      - post-init estilo nuevo:  (env)
      - post_init_hook clásico:  (cr, registry)
    """
    # Detecta si nos pasaron Environment o (cr, registry)
    if registry is None:
        # nos pasaron un Environment
        env = env_or_cr
    else:
        # nos pasaron (cr, registry)
        cr = env_or_cr
        env = api.Environment(cr, SUPERUSER_ID, {})

    _logger.warning(">>> Post-init: crear print_sequence_id en tipos OUT/INT")

    PType = env["stock.picking.type"].sudo()
    # candidatos: OUT/INT con almacén y UO, sin secuencia de impresión
    ptypes = PType.search([("code", "in", ("outgoing", "internal"))])
    ptypes_to_create = ptypes.filtered(
        lambda t: not t.print_sequence_id
        and t.warehouse_id
        and t.warehouse_id.operating_unit_id
    )

    _logger.warning(">>> Post-init: candidatos=%s", len(ptypes_to_create))
    if ptypes_to_create:
        # reutiliza tu método del modelo
        ptypes_to_create._ensure_print_sequence_with_ou()

    _logger.warning(">>> Post-init: FIN")
