"""Fail-closed JSON observation export with position lineage, not a GPS target extractor."""
import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_engine
from data_provenance import validate_measured_observations


def export_observations(session, observations, output):
    # Validate the ENTIRE dataset before touching output. Never silently drop a
    # rejected row and then advertise its remainder as a validated measurement set.
    if not isinstance(observations,list) or len(observations)>50000:
        raise ValueError("Expected at most 50000 explicitly measured observation records.")
    validate_measured_observations(session,observations)
    rendered=json.dumps(observations,indent=2,allow_nan=False)
    output=Path(output)
    temporary=None
    try:
        with NamedTemporaryFile(mode='w',encoding='utf-8',dir=output.parent,delete=False,suffix='.tmp') as handle:
            temporary=handle.name;handle.write(rendered)
        os.replace(temporary,output)
    finally:
        if temporary and Path(temporary).exists():Path(temporary).unlink()
    return len(observations)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():parser.error('Use a separate output path; input evidence is preserved.')
    observations=json.loads(args.input.read_text(encoding='utf-8'))
    with Session(get_engine()) as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        count=export_observations(session,observations,args.output)
    print(f'Exported {count} lineage-eligible records. Device authenticity/accuracy and target extraction remain unverified.')


if __name__=='__main__':main()
