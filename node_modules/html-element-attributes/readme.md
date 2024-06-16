# html-element-attributes

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]

Map of HTML elements to allowed attributes.

## Contents

*   [What is this?](#what-is-this)
*   [When should I use this?](#when-should-i-use-this)
*   [Install](#install)
*   [Use](#use)
*   [API](#api)
    *   [`htmlElementAttributes`](#htmlelementattributes)
*   [Types](#types)
*   [Compatibility](#compatibility)
*   [Security](#security)
*   [Related](#related)
*   [Contribute](#contribute)
*   [License](#license)

## What is this?

This is a map of tag names to lists of allowed attributes.
Global attributes are stored at the special tag name `*`.
All attributes from HTML 4 and the current living HTML spec are included.

> 👉 **Note**: Includes deprecated attributes.

> 👉 **Note**: Attributes which were not global in HTML 4 but are in HTML, are
> only included in the list of global attributes.

## When should I use this?

You can use this to figure out if certain attributes are allowed on certain
HTML elements.

## Install

This package is [ESM only][esm].
In Node.js (version 14.14+, 16.0+), install with [npm][]:

```sh
npm install html-element-attributes
```

In Deno with [`esm.sh`][esmsh]:

```js
import {htmlElementAttributes} from 'https://esm.sh/html-element-attributes@3'
```

In browsers with [`esm.sh`][esmsh]:

```html
<script type="module">
  import {htmlElementAttributes} from 'https://esm.sh/html-element-attributes@3?bundle'
</script>
```

## Use

```js
import {htmlElementAttributes} from 'html-element-attributes'

console.log(htmlElementAttributes['*'])
console.log(htmlElementAttributes.ol)
```

Yields:

```js
[
  'accesskey',
  'autocapitalize',
  'autofocus',
  'class',
  // …
  'style',
  'tabindex',
  'title',
  'translate'
]
['compact', 'reversed', 'start', 'type']
```

## API

This package exports the identifier `htmlElementAttributes`.
There is no default export.

### `htmlElementAttributes`

Map of lowercase HTML elements to allowed attributes
(`Record<string, Array<string>>`).

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

*   [`wooorm/web-namespaces`](https://github.com/wooorm/web-namespaces)
    — list of web namespaces
*   [`wooorm/html-tag-names`](https://github.com/wooorm/html-tag-names)
    — list of HTML tag names
*   [`wooorm/mathml-tag-names`](https://github.com/wooorm/mathml-tag-names)
    — list of MathML tag names
*   [`wooorm/svg-tag-names`](https://github.com/wooorm/svg-tag-names)
    — list of SVG tag names
*   [`wooorm/html-void-elements`](https://github.com/wooorm/html-void-elements)
    — list of void HTML tag names
*   [`wooorm/svg-element-attributes`](https://github.com/wooorm/svg-element-attributes)
    — map of SVG elements to attributes
*   [`wooorm/aria-attributes`](https://github.com/wooorm/aria-attributes)
    — list of ARIA attributes

## Contribute

Yes please!
See [How to Contribute to Open Source][contribute].

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definition -->

[build-badge]: https://github.com/wooorm/html-element-attributes/workflows/main/badge.svg

[build]: https://github.com/wooorm/html-element-attributes/actions

[coverage-badge]: https://img.shields.io/codecov/c/github/wooorm/html-element-attributes.svg

[coverage]: https://codecov.io/github/wooorm/html-element-attributes

[downloads-badge]: https://img.shields.io/npm/dm/html-element-attributes.svg

[downloads]: https://www.npmjs.com/package/html-element-attributes

[size-badge]: https://img.shields.io/bundlephobia/minzip/html-element-attributes.svg

[size]: https://bundlephobia.com/result?p=html-element-attributes

[npm]: https://docs.npmjs.com/cli/install

[esmsh]: https://esm.sh

[license]: license

[author]: https://wooorm.com

[esm]: https://gist.github.com/sindresorhus/a39789f98801d908bbc7ff3ecc99d99c

[typescript]: https://www.typescriptlang.org

[contribute]: https://opensource.guide/how-to-contribute/
