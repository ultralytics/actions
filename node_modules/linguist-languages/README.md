# linguist-languages

[![npm](https://img.shields.io/npm/v/linguist-languages.svg)](https://www.npmjs.com/package/linguist-languages)
[![build](https://img.shields.io/github/actions/workflow/status/ikatyang/linguist-languages/test.yml)](https://github.com/ikatyang/linguist-languages/actions?query=branch%3Amaster)

[Linguist `languages.yml`](https://github.com/github/linguist/blob/master/lib/linguist/languages.yml) in JSON format

## Install

```sh
npm install linguist-languages
```

## Usage

```js
import javascript from 'linguist-languages/data/JavaScript'
```

or

```js
import languages from 'linguist-languages'
const javascript = languages.JavaScript
```

## Development

```sh
# lint
pnpm run lint

# build
pnpm run build

# test
pnpm run test
```

## License

MIT © [Ika](https://github.com/ikatyang)
