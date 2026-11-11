"""Validate registry, provenance, canonical lists and generated unions."""
try:
    from .common import cli, validate, run
except ImportError:
    from common import cli, validate, run


def main():
    args = cli(__doc__).parse_args()
    outputs = validate(args.root)
    print('OK: registry, sources, formats, IPv4 policy, overlaps and combined lists')
    for kind, values in outputs.items():
        print(f'{kind}: {len(values)}')


if __name__ == '__main__':
    run(main)
