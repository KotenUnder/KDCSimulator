import json

with open('KDC_table.json', 'r') as f:
    kdc_table = json.load(f)

KDC_sine_table = kdc_table['sin']
KDC_arctan_table = kdc_table['arctan']
KDC_slope_table = kdc_table['terrain_to_slope']

KDC_Zoffset_table = kdc_table['z_offset']

KDC_power_grounder_table = kdc_table['power_ground']
KDC_power_popup_table = kdc_table['power_popup']
