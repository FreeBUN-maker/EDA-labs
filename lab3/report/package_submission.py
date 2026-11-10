#!/usr/bin/env python3
"""Package only README, source/evidence, and the report; exclude build outputs."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json
import shutil

LAB = Path(__file__).resolve().parent.parent
HANDIN = LAB / 'handin'
RUN = HANDIN / 'hw3_run'
REFERENCE = HANDIN / 'src' / 'reference_results'


def main():
    report = json.loads((RUN / 'flow_report.json').read_text())
    assert report['pass'] and report['flow_exit'] == 0
    assert 'RESULT: PASS' in (RUN / 'check.log').read_text()
    REFERENCE.mkdir(exist_ok=True)
    for name in ('macro_placement.json', 'macro_placement.tcl', 'flow_report.json',
                 'partition_analysis.json', 'search_config.json', 'environment.json',
                 'student.log', 'flow.log', 'check.log', 'check_macro.log'):
        shutil.copy2(RUN / name, REFERENCE / name)
    shutil.copy2(HANDIN / 'theory_results.json', REFERENCE / 'theory_results.json')
    shutil.copy2(LAB / 'report' / 'lab3_report.pdf', HANDIN / 'hw3-2300012831.pdf')
    paths = [HANDIN / 'README.md', HANDIN / 'hw3-2300012831.pdf']
    paths += sorted(p for p in (HANDIN / 'src').rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts
                    and p.suffix != '.pyc' and p.name != '.DS_Store')
    archive = LAB / 'hw3-2300012831.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=9) as z:
        for p in paths:
            z.write(p, p.relative_to(HANDIN))
    with ZipFile(archive) as z:
        assert z.testzip() is None
        assert {name.split('/')[0] for name in z.namelist()} == {
            'README.md', 'src', 'hw3-2300012831.pdf'}
    print(f'{archive}: {len(paths)} files, {archive.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
