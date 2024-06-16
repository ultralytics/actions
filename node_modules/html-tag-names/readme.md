# html-tag-names

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]

List of known HTML tag names.

## Contents

*   [What is this?](#what-is-this)
*   [When should I use this?](#when-should-i-use-this)
*   [Install](#install)
*   [Use](#use)
*   [API](#api)
    *   [`htmlTagNames`](#htmltagnames)
*   [Types](#types)
*   [Compatibility](#compatibility)
*   [Security](#security)
*   [Related](#related)
*   [Contribute](#contribute)
*   [License](#license)

## What is this?

This is a list of HTML tag names.
It includes ancient (for example, `nextid` and `basefont`) and modern (for
example, `shadow` and `template`) names from the HTML living standard.
The repo includes scripts to regenerate the data from the specs.

## When should I use this?

You can use this package when you need to know what tag names are allowed in
any version of HTML.

## Install

This package is [ESM only][esm].
In Node.js (version 14.14+, 16.0+), install with [npm][]:

```sh
npm install html-tag-names
```

In Deno with [`esm.sh`][esmsh]:

```js
import {htmlTagNames} from 'https://esm.sh/html-tag-names@2'
```

In browsers with [`esm.sh`][esmsh]:

```html
<script type="module">
  import {htmlTagNames} from 'https://esm.sh/html-tag-names@2?bundle'
</script>
```

## Use

```js
import {htmlTagNames} from 'html-tag-names'

console.log(htmlTagNames.length) // => 148

console.log(htmlTagNames.slice(0, 20))
```

Yields:

```js
[
  'a',
  'abbr',
  'acronym',
  'address',
  'applet',
  'area',
  'article',
  'aside',
  'audio',
  'b',
  'base',
  'basefont',
  'bdi',
  'bdo',
  'bgsound',
  'big',
  'blink',
  'blockquote',
  'body',
  'br'
]
```

## API

This package exports the identifier `htmlTagNames`.
There is no default export.

### `htmlTagNames`

List of known (lowercase) HTML tag names (`Array<string>`).

## Types

This package is fully typed with [TypeScript][].
It exports no additional types.

## Compatibility

This package is at least compatible with all maintained versions of Node.js.
As of now, that is Node.js 14.14+ and 16.0+.
It also works in Deno and modern browsers.

## Security

This package is safe.

## Related

*   [`wooorm/mathml-tag-names`](https://github.com/wooorm/mathml-tag-names)
    — list of MathML tag names
*   [`wooorm/svg-tag-names`](https://github.com/wooorm/svg-tag-names)
    — list of SVG tag names
*   [`jgierer12/react-tag-names`](https://github.com/jgierer12/react-tag-names)
    — list of React’s HTML and SVG tag names
*   [`wooorm/svg-element-attributes`](https://github.com/wooorm/svg-element-attributes)
    — map of SVG elements to attributes
*   [`wooorm/html-element-attributes`](https://github.com/wooorm/html-element-attributes)
    — map of HTML elements to attributes
*   [`wooorm/aria-attributes`](https://github.com/wooorm/aria-attributes)
    — list of ARIA attributes

## Contribute

Yes please!
See [How to Contribute to Open Source][contribute].

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definition -->

[build-badge]: https://github.com/wooorm/html-tag-names/workflows/main/badge.svg

[build]: https://github.com/wooorm/html-tag-names/actions

[coverage-badge]: https://img.shields.io/codecov/c/github/wooorm/html-tag-names.svg

[coverage]: https://codecov.io/github/wooorm/html-tag-names

[downloads-badge]: https://img.shields.io/npm/dm/html-tag-names.svg

[downloads]: https://www.npmjs.com/package/html-tag-names

[size-badge]: https://img.shields.io/bundlephobia/minzip/html-tag-names.svg

[size]: https://bundlephobia.com/result?p=html-tag-names

[npm]: https://docs.npmjs.com/cli/install

[esmsh]: https://esm.sh

[license]: license

[author]: https://wooorm.com

[esm]: https://gist.github.com/sindresorhus/a39789f98801d908bbc7ff3ecc99d99c

[typescript]: https://www.typescriptlang.org

[contribute]: https://opensource.guide/how-to-contribute/
