"""Entry point: `html2epub-server` -- starts the loopback conversion server."""

from __future__ import annotations

import logging

from html_to_epub_server.config import DEFAULT_CONFIG_PATH, load_or_create_config
from html_to_epub_server.handler import create_server


def main() -> None:
    """Start the server, printing config path/port/output_dir, until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = load_or_create_config(DEFAULT_CONFIG_PATH)

    print(f"config: {DEFAULT_CONFIG_PATH}")
    print(f"port: {config.port}")
    print(f"output_dir: {config.output_dir}")

    server = create_server(config)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
