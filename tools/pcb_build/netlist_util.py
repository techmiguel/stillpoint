import xml.etree.ElementTree as ET
import os
import pcbnew

KICAD_FP = r"C:/Program Files/KiCad/10.0/share/kicad/footprints"
PRJ_FP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "lib", "radar60.pretty")


def load_netlist(path):
    r = ET.parse(path).getroot()
    comps = {}
    for c in r.find('components'):
        ref = c.get('ref')
        fields = {}
        fe = c.find('fields')
        if fe is not None:
            for x in fe:
                fields[x.get('name')] = x.text or ''
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        comps[ref] = dict(value=c.findtext('value'), fp=c.findtext('footprint'),
                          datasheet=c.findtext('datasheet') or '',
                          description=c.findtext('description') or '',
                          fields=fields, props=props,
                          tstamp=(c.findtext('tstamps') or '').split()[0])
    nets = {}
    for n in r.find('nets'):
        nets[n.get('name')] = [(x.get('ref'), x.get('pin')) for x in n.findall('node')]
    return comps, nets


def fp_load(libid):
    lib, name = libid.split(':')
    path = PRJ_FP if lib == 'radar60' else os.path.join(KICAD_FP, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError('footprint not found ' + libid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp
