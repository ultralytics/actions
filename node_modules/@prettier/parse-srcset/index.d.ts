export type Candidate = {
  source: {
    value: string;
    startOffset: number;
  };
  width?: {
    value: number;
  };
  height?: {
    value: number;
  };
  density?: {
    value: number;
  };
};

/**
Parses the string value that appears in markup `<img srcset="here">`.

@description A javascript parser for the [HTML5 srcset](http://www.w3.org/TR/html-srcset/) attribute, based on the [WHATWG reference algorithm](https://html.spec.whatwg.org/multipage/embedded-content.html#parse-a-srcset-attribute). It has an extensive test suite based on the [W3C srcset conformance checker](http://w3c-test.org/html/semantics/embedded-content/the-img-element/srcset/parse-a-srcset-attribute.html)

@param {string} input - The string value to parse.
@returns {Candidate[]} An array of objects representing the image candidates.
@throws {Error} If the input string is empty or does not contain any image candidate strings.

@example
```ts
import parseSrcset from "@prettier/parse-srcset";

parseSrcset('elva-fairy-320w.jpg, elva-fairy-480w.jpg 1.5x, elva-fairy-640w.jpg 2x');
// output:
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
```
*/
export default function parseSrcset(input: string): Candidate[];
