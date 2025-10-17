# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import math


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Cantidad de líneas para albaranes OUT (entregas) - guardado en ir.config_parameter
    preprint_lines_out = fields.Integer(
        string="Líneas por albarán de entregas",
        config_parameter="stock_preprinted_delivery.preprint_lines_out",  # clave del parámetro
        default=25,  # valor por defecto razonable
        help="Cantidad de renglones impresos en remitos/albaranes OUT (entregas).",
    )

    # Cantidad de líneas para albaranes INT (mov. internos) - guardado en ir.config_parameter
    preprint_lines_int = fields.Integer(
        string="Líneas por albarán internos",
        config_parameter="stock_preprinted_delivery.preprint_lines_int",
        default=25,
        help="Cantidad de renglones impresos en remitos/albaranes INT (movimientos internos).",
    )


def _valid_moves(picking):
    """Líneas a considerar: no canceladas/terminadas y con cantidades."""
    return picking.move_ids.filtered(
        lambda m: m.state not in ('cancel', 'done') and (m.product_uom_qty or m.quantity_done)
    )

    
class AlbaranPrintHelloWizard(models.TransientModel):
    _name = "albaran.print.hello.wizard"
    _description = "Wizard de impresión - Hola"

    message = fields.Char(
        string="Mensaje",
        default="Hola mundo",
        readonly=True
    )
    picking_id = fields.Many2one("stock.picking", string="Albarán", required=True, readonly=True)
    picking_type_code = fields.Selection(related="picking_id.picking_type_code", readonly=True)
    total_lines = fields.Integer(string="Líneas totales", compute="_compute_totals", store=False)
    lines_per_doc = fields.Integer(string="Líneas por documento", required=True)
    expected_docs = fields.Integer(string="Remitos esperados", compute="_compute_totals", store=False)
    detail_note = fields.Html(string="Detalle", sanitize=False, readonly=True)
    sequence_id = fields.Many2one("ir.sequence", string="Secuencia de impresión", readonly=True)
    next_numbers_preview = fields.Text(string="Próximos números", readonly=True)
    
    @api.depends("picking_id", "lines_per_doc")
    def _compute_totals(self):
        for w in self:
            if not w.picking_id:
                w.total_lines = 0; w.expected_docs = 0; continue
            moves = w.picking_id.move_ids.filtered(
                lambda m: m.state != "cancel" and (m.product_uom_qty or m.quantity_done)
            )
            total = len(moves)
            lpd = max(w.lines_per_doc or 1, 1)
            w.total_lines = total
            w.expected_docs = math.ceil(total / lpd) if total else 0


    # SOLO split por N líneas (sin secuencias). Odoo 17.

    def action_confirm_preprint(self):
        """Parte el albarán en lotes de 'lines_per_doc' (primer lote queda en el original)."""
        self.ensure_one()
        p   = self.picking_id
        lpd = max(self.lines_per_doc or 1, 1)  # evita 0
        moves = p.move_ids          # En teoría traigo el recordsets no una lista
        total = len(p.move_ids.ids)
        if total <= lpd:
            ###### NADA QUE SEPARAR SOLO SE LE VA  A ASIGNAR EL VALOR DE LA SEQ DE IMPRESIÓN. Y MANDAR A IMPRESIÓN
            return {
            "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": "Split", "message": "No se requiere split.", "type": "success"},
            }

      
        #### PROCESO PARA SEPARAR LOS REMITOS Y LUEGO DE SEPARADOS CON LOS ID DE LOS PICKING GENERADOS ASIGNAR LAS SECUENCIAS DE IMPRESIÓN E IMPRIMIR.

      
        
        batches = [moves[i:i + lpd] for i in range(0, total, lpd)]  # chunks

        #raise UserError(f"Picking actual: {p.name} lineas {len(p.move_ids.ids)} Tope  de lineas: {lpd}. Total de lineas reales; {total}  /n Bloques {batches}")
      
        created = self.env['stock.picking']
        for batch in batches[1:]:
            # al crear cada nuevo albarán (en el split), copiá también la secuencia:
            new_pick = p.copy({"name": "/", "move_ids": [], "print_sequence_id": (p.print_sequence_id or p.picking_type_id.print_sequence_id).id})
            # copia del picking SIN movimientos
            #new_pick = p.copy({"name": "/", "move_ids": []})
            # reasigna los movimientos del lote al nuevo picking
            batch.write({"picking_id": new_pick.id})
            # mover líneas de operación (clave para que el reporte las vea)
            batch.mapped("move_line_ids").write({"picking_id": new_pick.id})
            created |= new_pick

        # dentro de action_confirm_preprint, LUEGO del split (tenés p y created/new_picks)

        # 1) asegurar secuencia de impresión en cada picking (original + nuevos)
        for pk in (p | created):
            if not pk.print_sequence_id:
                pk.write({'print_sequence_id': (pk.picking_type_id.print_sequence_id or False)})
            if not pk.print_sequence_id:
                raise UserError(f"Sin secuencia de impresión en {pk.display_name}")

        for pk in (p | created):
            if not pk.print_folio:
               seq_id = pk.print_sequence_id
               folio = pk.write({'print_folio': seq_id.number_next_actual})  # guarda el número formateado
               actualiza = seq_id.write({'number_next_actual': (seq_id.number_next_actual + seq_id.number_increment)})


        # después del split (tenés: p = original, created = nuevos)
        pickings_to_print = p | created

        # 1) confirmar (de draft a confirmed)
        #pickings_to_print.action_confirm()     # crea moves en estado correcto

        for pk in pickings_to_print:
            pk.action_confirm()
            pk.with_context(skip_immediate=True).button_validate()  # valida cada albarán
            #pk.action_assign() # Comprobamos disponibilidad
        # 2) asignar (reserva y genera move_line_ids de operaciones)
        # pickings_to_print._action_assign()

        # 3) imprimir
        if p.picking_type_code == 'outgoing':
            return self.env.ref('stock.action_report_delivery').report_action(pickings_to_print.ids)
        else:
            return self.env.ref('stock.action_report_picking').report_action(pickings_to_print.ids)

        # feedback: cantidad + nombres
        #names = ", ".join([(n or "(sin nombre)") for n in created.mapped("name")])
        #names = ", ".join(created.mapped("display_name")) or "-"
        names = ", ".join(created.mapped("name")) or "-"
        msg = f"Generados {1 + len(created)} albaranes. Nuevos: {names}"
            
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Split",
                "message": f"Generados {1 + len(created)} albaranes (original + {len(created)} nuevos).",
                "type": "success",
            },
        }

        





#############################################################

#    def action_confirm_preprint(self):

        # """Parte el albarán en bloques de 'lines_per_doc' y asigna folios de impresión."""
        # self.ensure_one()
        # p = self.picking_id
        # lpd = max(self.lines_per_doc or 1, 1)                      # evita división por cero       
        # # --- Secuencia de impresión y campos destino en stock.picking ---
        # seq = p.picking_type_id.print_sequence_id                  # ir.sequence definida en el tipo
        # has_seq_field = 'print_sequence_id' in p._fields           # M2O a ir.sequence
        # has_folio_field = 'print_folio' in p._fields               # Char con el folio consumido
        # # raise UserError(f"Picking: {p.id}, Linea por documento {lpd} \n Secuencia {seq}")
        # # --- Garantiza que el picking original tenga seteada la secuencia a usar ---
        # if seq and has_seq_field and (not p.print_sequence_id or p.print_sequence_id.id != seq.id):
        #     p.write({'print_sequence_id': seq.id})

        # # --- Partición de movimientos en lotes (primer lote queda en el original) ---
        # moves = _valid_moves(p)
        # total = len(moves)
        # new_picks = self.env['stock.picking']
        # if total > lpd:
        #     batches = [moves[i:i + lpd] for i in range(0, total, lpd)]
        #     for batch in batches[1:]:
        #         # copia del picking SIN líneas para alojar el lote
        #         vals_copy = {"name": False, "move_ids": []}
        #         if seq and has_seq_field:
        #             vals_copy["print_sequence_id"] = seq.id        # misma secuencia en el nuevo
        #         np = p.copy(vals_copy)
        #         batch.write({"picking_id": np.id})                 # reasigna líneas al nuevo picking
        #         new_picks |= np

        # # --- Consume y asigna folios (formateados) a todos los pickings resultantes ---
        # if seq and has_folio_field:
        #     seq_env = self.env['ir.sequence'].with_context(        # respeta rangos por fecha
        #         ir_sequence_date=fields.Date.context_today(self)
        #     )
        #     for pk in (p | new_picks):
        #         if not pk.print_folio:                             # no duplicar consumo
        #             pk.write({'print_folio': seq_env.next_by_id(seq.id)})

        # # --- Feedback visual ---
        # total_docs = 1 + len(new_picks)
        # return {
        #     "type": "ir.actions.client",
        #     "tag": "display_notification",
        #     "params": {
        #         "title": "Split y folio",
        #         "message": f"{total_docs} albarán(es) generados y foliados.",
        #         "type": "success",
        #     },
        # }

##########################################


        # self.ensure_one()
        # return {
        # "type": "ir.actions.client",
        # "tag": "display_notification",
        # "params": {"title": "OK", "message": "Confirmado", "type": "success"},
        # "context": {"default_picking_id": self.id}, 
        # }

class StockPicking(models.Model):
    _inherit = "stock.picking"
    # secuencia elegida para foliar este picking (no avanza contador)
    print_sequence_id = fields.Many2one(
        "ir.sequence", string="Secuencia de impresión", copy=False
    )
    # número asignado al consumir la secuencia (siguiente formateado)
    print_folio = fields.Char(string="Folio de impresión", copy=False, index=True)


    
    def action_print_intercept(self):
        self.ensure_one()
        if self.picking_type_code not in ("outgoing", "internal"):
            raise UserError("Solo disponible para albaranes OUT o INT.")

        # leer parámetros para líneas por doc
        ICP = self.env["ir.config_parameter"].sudo()
        if self.picking_type_code == "outgoing":
            lpd = int(ICP.get_param("stock_preprinted_delivery.preprint_lines_out", default=25))
        elif self.picking_type_code == "internal":
            lpd = int(ICP.get_param("stock_preprinted_delivery.preprint_lines_int", default=25))
        else:
            lpd = 25

        # 1) Total de líneas (ajusta a move_line si lo usás)
        moves = self.move_ids.filtered(lambda m: m.state != "cancel" and (m.product_uom_qty or m.quantity_done))
        total = len(moves)    

        # 2) Remitos esperados
        expected_docs = math.ceil(total / max(lpd, 1)) if total else 0

            
        # (supuesto) el tipo de operación tiene la secuencia en este campo:
        seq = self.picking_type_id.print_sequence_id
        
        next_list = []
        if seq and expected_docs:
            cur = seq._get_current_sequence() if hasattr(seq, "_get_current_sequence") else seq
            start = (cur.number_next_actual or seq.number_next_actual or 1)
            step  = (cur.number_increment or seq.number_increment or 1)
            for i in range(expected_docs):
                # get_next_char formatea con prefijo/sufijo sin avanzar el contador
                next_list.append(seq.get_next_char(start + i * step))


        # crear el wizard con valores iniciales
        wiz = self.env["albaran.print.hello.wizard"].create({
            "picking_id": self.id,
            "lines_per_doc": lpd,
            "sequence_id": seq.id if seq else False,
            "next_numbers_preview": "\n".join(next_list),  # o HTML si prefieres
            "message": "Hola mundoooo",
        })

        # abrir ese registro
        view = self.env.ref("stock_preprinted_delivery_settings.view_albaran_print_hello_wizard")
        return {
            "type": "ir.actions.act_window",
            "name": "Imprimir",
            "res_model": "albaran.print.hello.wizard",
            "view_mode": "form",
            "view_id": view.id,
            "res_id": wiz.id,
            "target": "new",
        }

def _slug(text):                                      # normaliza texto para usar en code/prefix
    text = (text or "").strip().upper()               # mayúsculas y trim
    return "".join(ch for ch in text if ch.isalnum()) # solo A-Z0-9

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    print_sequence_id = fields.Many2one(           # secuencia de impresión (ya creada en el paso anterior)
        "ir.sequence",
        string="Secuencia de impresión",
        help="Secuencia usada para foliar el impreso (no afecta la referencia del albarán).",
        domain="[('company_id','in',[False, company_id])]",
    )

    def _ensure_print_sequence_with_ou(self):      # crea/asigna secuencia con tipo + UO en code
        for ptype in self:                         # iterar tipos seleccionados
            if ptype.print_sequence_id:            # si ya existe, no crear de nuevo
                continue
            ou = ptype.warehouse_id and ptype.warehouse_id.operating_unit_id  # trae UO desde almacén
            if not ou:                             # si no hay UO, no forzar creación
                continue
            type_key = _slug(ptype.code or "ALB")  # clave del tipo (OUT/INT/…)
            ou_key   = _slug(ou.name or ou.code or f"OU{ou.id}")  # clave de la UO
            seq_code = f"print.{type_key}.{ou_key}"               # code interno con tipo y UO
            prefix   = f"{type_key}/{ou_key}/"                    # prefijo visible, ej: OUT/CORDOBA/
            seq = self.env["ir.sequence"].create({                # crear secuencia
                "name": f"Print {ptype.name} - {ou.name}",        # nombre legible
                "implementation": "standard",                     # estándar
                "prefix": prefix,                                 # prefijo con tipo+UO
                "padding": 6,                                     # 000001
                "company_id": ptype.company_id.id or False,       # compañía del tipo
                "code": seq_code,                                 # code interno con tipo+UO
            })
            ptype.print_sequence_id = seq.id                      # asigna al tipo

    @api.model_create_multi
    def create(self, vals_list):                  # (opcional, pero útil) al crear el tipo, asegurar secuencia
        records = super().create(vals_list)       # crea tipos
        records._ensure_print_sequence_with_ou()  # genera secuencia con tipo+UO (si hay UO)
        return records

