"""Build enabled service unions without widening subnet coverage."""
try:
    from .common import cli, combined, load_config, atomic_write, encode, run
except ImportError:
    from common import cli, combined, load_config, atomic_write, encode, run


def build(root, check=False):
    services, _ = load_config(root)
    outputs = combined(root, services)
    for kind, values in outputs.items():
        path = root / kind / 'all.txt'
        if check:
            if not path.exists() or path.read_bytes() != encode(values):
                raise ValueError(f'{path}: combined list differs')
        else:
            atomic_write(path, encode(values))
        print(f'{kind}/all.txt: {len(values)} records')


def main():
    parser = cli(__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    build(args.root, args.check)


if __name__ == '__main__':
    run(main)
