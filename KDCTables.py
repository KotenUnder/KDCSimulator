import json

with open('KDC_table.json', 'r') as f:
    kdc_table = json.load(f)

KDC_sine_table = kdc_table['sin']
KDC_arctan_table = kdc_table['arctan']
