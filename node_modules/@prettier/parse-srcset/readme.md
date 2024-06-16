# @prettier/parse-srcset

This repository is a fork of https://github.com/albell/parse-srcset for [Prettier](https://github.com/prettier/prettier).

---

A javascript parser for the [HTML5 srcset](http://www.w3.org/TR/html-srcset/) attribute, based on the [WHATWG reference algorithm](https://html.spec.whatwg.org/multipage/embedded-content.html#parse-a-srcset-attribute). It has an extensive test suite based on the [W3C srcset conformance checker](http://w3c-test.org/html/semantics/embedded-content/the-img-element/srcset/parse-a-srcset-attribute.html).

## Installation

```bash
yarn add @prettier/parse-srcset
```

## Usage

```js
import parseSrcset from "@prettier/parse-srcset";

parseSrcset('elva-fairy-320w.jpg, elva-fairy-480w.jpg 1.5x, elva-fairy-640w.jpg 2x');
/*
[
  { source: { value: 'elva-fairy-320w.jpg', startOffset: 0 } },
  {
    source: { value: 'elva-fairy-480w.jpg', startOffset: 21 },
    density: { value: 1.5 }
  },
  {
    source: { value: 'elva-fairy-640w.jpg', startOffset: 47 },
    density: { value: 2 }
  }
]
*/
```
