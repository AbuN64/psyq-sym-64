# psyq-sym-64

Reads the Psy-Q SYM debug records some N64 ROMs still carry and writes their functions, structs, typedefs and enums as JSON.

> This is a personal tool. It is not officially maintained and may change or break without notice.

## Install

```sh
pip install git+https://github.com/AbuN64/psyq-sym-64
```

## Usage

```sh
psyq-sym --config debug-symbols.toml --version us --locate
psyq-sym --config debug-symbols.toml --version us > names.json
```

The first form finds the record runs in the ROM. Save their ranges in the config, then the second writes the names. Run `psyq-sym --help` for the rest.

The same package decodes the Psy-Q LNK object record stream some ROMs keep as overlay images (code chunks, patches, source-line records): `psyq_sym.lnk.locate(rom_slice)` returns where the stream starts and its records.

## Development

Run `PYTHONPATH=src python -m pytest tests`.

## Credits

The record format follows [mefistotelis/psx_mnd_sym](https://github.com/mefistotelis/psx_mnd_sym), whose `sym_dump` is the test oracle.

## License

Released into the public domain ([UNLICENSE](UNLICENSE)).
