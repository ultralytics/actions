# yaml-unist-parser

[![npm](https://img.shields.io/npm/v/yaml-unist-parser.svg)](https://www.npmjs.com/package/yaml-unist-parser)
[![build](https://img.shields.io/github/workflow/status/prettier/yaml-unist-parser/CI)](https://github.com/prettier/yaml-unist-parser/actions?query=workflow%3ACI+branch%3Amain)
[![coverage](https://img.shields.io/codecov/c/github/prettier/yaml-unist-parser/main.svg)](https://codecov.io/gh/prettier/yaml-unist-parser)

A YAML parser that produces output compatible with [unist](https://github.com/syntax-tree/unist)

[Changelog](https://github.com/ikatyang/yaml-unist-parser/blob/master/CHANGELOG.md)

## Features

- better node positioning
- better comment attaching
- [unist-compatible AST](https://github.com/ikatyang/yaml-unist-parser/blob/master/src/types.ts)

## Install

```sh
# using npm
npm install --save yaml-unist-parser

# using yarn
yarn add yaml-unist-parser
```

## Usage

```ts
import { parse } from "yaml-unist-parser";

const ast = parse(`
- hello
- world
`);
```

## Development

```sh
# lint
yarn run lint

# build
yarn run build

# test
yarn run test
```

## License

MIT © [Ika](https://github.com/ikatyang)
