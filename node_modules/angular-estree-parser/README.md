# angular-estree-parser

[![Build Status][github_actions_badge]][github_actions_link]
[![Coverage][coverage_badge]][coverage_link]
[![Npm Version][package_version_badge]][package_link]
[![MIT License][license_badge]][license_link]

[github_actions_badge]: https://img.shields.io/github/actions/workflow/status/prettier/angular-estree-parser/ci.yml
[github_actions_link]: https://github.com/prettier/angular-estree-parser/actions?query=workflow%3ACI+branch%3Amain
[coverage_badge]: https://img.shields.io/codecov/c/github/prettier/angular-estree-parser/main.svg
[coverage_link]: https://codecov.io/gh/prettier/angular-estree-parser
[license_badge]: https://img.shields.io/npm/l/angular-estree-parser.svg
[license_link]: https://github.com/prettier/angular-estree-parser/blob/main/LICENSE
[package_version_badge]: https://img.shields.io/npm/v/angular-estree-parser.svg
[package_link]: https://www.npmjs.com/package/angular-estree-parser

A parser that converts Angular source code into an ESTree-compatible form

[Changelog](https://github.com/prettier/angular-estree-parser/blob/main/CHANGELOG.md)

## Install

```sh
# using npm
npm install --save angular-estree-parser @angular/compiler

# using yarn
yarn add angular-estree-parser @angular/compiler
```

## Usage

```js
import * as ngEstreeParser from 'angular-estree-parser';

const ast = ngEstreeParser.parseBinding('a | b:c');
//=> { type: "NGPipeExpression", ... }
```

## API

- `parseAction(input: string): AST` for `(target)="input"`
- `parseBinding(input: string): AST` for `[target]="input"`
- `parseInterpolationExpression(input: string): AST` for `{{input}}`
- `parseTemplateBindings(input: string): AST` for `*directive="input"`

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
