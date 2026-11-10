#!/usr/bin/env python3
"""Rebuild report figures from recorded experiment data (matplotlib)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parent
ASSET = ROOT / 'asset'
HANDIN = ROOT.parent / 'handin'
THEORY = json.loads((HANDIN / 'theory_results.json').read_text())
plt.rcParams.update({'font.size': 10, 'font.family': 'DejaVu Sans',
                     'pdf.fonttype': 42, 'savefig.bbox': 'tight'})
COLORS = ['#247ba0', '#b56576', '#e09f3e', '#4d9078', '#665191', '#dd8452', '#4878a8', '#79706e']


def sp_graph(kind):
    d = THEORY['problem2']
    fig, ax = plt.subplots(figsize=(7, 6.7))
    pos = {i: np.array([d['P'].index(i) + d['N'].index(i) - 7,
                       d['N'].index(i) - d['P'].index(i)], float) for i in range(1, 9)}
    for k in range(8):
        ax.plot([k-7, k], [-k, 7-k], color='#d9dee3', lw=.7, zorder=0)
        ax.plot([k-7, k], [k, k-7], color='#d9dee3', lw=.7, zorder=0)
    ax.plot([-7, 0, 7, 0, -7], [0, 7, 0, -7, 0], color='#9ba8b3', lw=1)
    for k, i in enumerate(d['P']):
        ax.text(k-7.6, -k-.55, str(i), ha='center', va='center', color='#566573', rotation=-45)
    for k, i in enumerate(d['N']):
        ax.text(k+.6, k-7.55, str(i), ha='center', va='center', color='#566573', rotation=45)
    ax.text(-5.3, -5.3, 'Positive sequence P', rotation=-45, rotation_mode='anchor',
            ha='center', va='center', color='#566573')
    ax.text(5.3, -5.3, 'Negative sequence N', rotation=45, rotation_mode='anchor',
            ha='center', va='center', color='#566573')
    edges = d[kind]
    for idx, (u, v, w) in enumerate(edges):
        a, b = pos[u], pos[v]
        # Curve the long edges away from intermediate vertices.
        dist = np.linalg.norm(b-a)
        rad = (0.11 if idx % 2 else -0.11) if dist > 4 else 0
        t = .34 + .1 * (idx % 3)
        if kind == 'horizontal':
            rad, t = {(7, 6): (-.25, .4), (7, 3): (-.35, .3),
                      (4, 6): (.35, .3), (4, 3): (.25, .4)}.get(
                          (u, v), (0, .25 if a[1] != b[1] else .5))
        color = COLORS[u-1]
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=11,
                                     connectionstyle=f'arc3,rad={rad}',
                                     shrinkA=13, shrinkB=13, color=color, lw=1.25, zorder=2))
        delta = b-a
        control = (a+b)/2 + rad*np.array([delta[1], -delta[0]])
        label = (1-t)**2*a + 2*t*(1-t)*control + t*t*b
        ax.text(*label, str(w), ha='center', va='center', fontsize=9, color=color,
                bbox=dict(facecolor='white', edgecolor='none', pad=.65, alpha=.95), zorder=4)
    if kind == 'horizontal':
        pos['s'], pos['t'] = np.array([-8.2, 0]), np.array([8.2, 0])
        widths = {m['i']: m['w'] for m in d['modules']}
        extra = [('s', i, 0) for i in range(1,9) if not any(v==i for u,v,w in edges)]
        extra += [(i, 't', widths[i]) for i in range(1,9) if not any(u==i for u,v,w in edges)]
    else:
        pos['s'], pos['t'] = np.array([0, 8.4]), np.array([0, -8.4])
        extra = [('s', 1, 0), (8, 't', 4)]
    for u, v, w in extra:
        a, b = pos[u], pos[v]
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,
                                     shrinkA=12,shrinkB=12,lw=1,color='#7e8c97',zorder=1))
        c = .48*a+.52*b
        ax.text(c[0],c[1]+.15,str(w),fontsize=8,color='#677682',ha='center',
                bbox=dict(facecolor='white',edgecolor='none',pad=.3),zorder=4)
    for i, xy in pos.items():
        if isinstance(i, int):
            ax.add_patch(Circle(xy,.34,facecolor='white',edgecolor=COLORS[i-1],lw=1.7,zorder=5))
        ax.text(*xy,str(i),ha='center',va='center',fontsize=12,zorder=6)
    ax.set(xlim=(-9.5,9.5),ylim=(-9,9),aspect='equal')
    ax.axis('off')
    fig.savefig(ASSET / f'{kind}_graph.pdf')
    fig.savefig(ROOT / 'tmp' / f'{kind}_graph.png', dpi=130)
    plt.close(fig)


def packing():
    d = THEORY['problem2']
    fig, ax = plt.subplots(figsize=(5, 6))
    for m in d['modules']:
        ax.add_patch(Rectangle((m['x'],m['y']),m['w'],m['h'],
                               facecolor=COLORS[m['i']-1],edgecolor='white',lw=1.7,alpha=.85))
        ax.text(m['x']+m['w']/2,m['y']+m['h']/2,str(m['i']),ha='center',va='center',
                color='white',weight='bold',fontsize=13)
    ax.add_patch(Rectangle((0,0),d['W'],d['H'],fill=False,edgecolor='#253746',lw=1.4))
    ax.set(xlim=(-.25,11.25),ylim=(-.25,15.25),aspect='equal',xlabel='x',ylabel='y',
           xticks=range(0,12),yticks=range(0,16))
    ax.grid(alpha=.12)
    ax.set_axisbelow(True)
    fig.savefig(ASSET / 'problem2_packing.pdf')
    plt.close(fig)


def macro_plot():
    run = HANDIN / 'hw3_run'
    if not (run / 'partition_analysis.json').exists():
        return
    p = json.loads((run / 'macro_placement.json').read_text())
    a = json.loads((run / 'partition_analysis.json').read_text())
    names = sorted(p['macros'])
    sizes = {m['name']: m for m in a['macros']}
    fig, ax = plt.subplots(figsize=(5,6))
    for i, name in enumerate(names):
        m, s = p['macros'][name], sizes[name]
        ax.add_patch(Rectangle((m['x'],m['y']),s['w'],s['h'],
                               facecolor=COLORS[i],edgecolor='#ffffff',lw=1.5,alpha=.85))
        ax.text(m['x']+s['w']/2,m['y']+s['h']/2,f'M{i+1}\n{m["orient"]}',
                ha='center',va='center',color='white',fontsize=13,linespacing=1.6)
    x0,y0,x1,y1 = p['core']
    ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#253746',lw=1.4))
    ax.set(xlim=(-40,x1+40),ylim=(-40,y1+40),aspect='equal',xlabel='x (um)',ylabel='y (um)',
           xticks=[0,1000,2000],yticks=[0,1000,2000,3000])
    ax.grid(alpha=.15)
    ax.set_axisbelow(True)
    fig.savefig(ASSET / 'macro_floorplan.pdf')
    plt.close(fig)


if __name__ == '__main__':
    ASSET.mkdir(exist_ok=True)
    sp_graph('horizontal')
    sp_graph('vertical')
    packing()
    macro_plot()
