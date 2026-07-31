try:
    from .converter_core import load_config, run_conversion
except ImportError:  # pragma: no cover - standalone script compatibility
    from converter_core import load_config, run_conversion


def main():
    run_conversion(load_config())


if __name__ == "__main__":
    main()
