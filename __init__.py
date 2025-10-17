# -*- coding: utf-8 -*-
# Carga de submódulos de Python del addon
from . import models
from .hooks import post_init_set_print_sequences_on_types  # <-- EXPUESTO AQUÍ
