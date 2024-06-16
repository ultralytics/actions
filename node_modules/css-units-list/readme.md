# css-units-list

> List of CSS:Cascading Style Sheets Units

Data from [CSS Values and Units Module Level 4](https://www.w3.org/TR/css-values-4/)

## Install

```bash
yarn add css-units-list
```

## Usage

```js
import cssUnits from 'css-units-list'

console.log(cssUnits)

// => [ 'em', 'rem', 'ex', 'rex', 'cap', 'rcap', ...]
```

```js
import {
  fontRelativeLengths,
  viewportPercentageLengths,
  relativeLengths,
  absoluteLengths,
  angleUnits,
  durationUnits,
  frequencyUnits,
  resolutionUnits,
  containerRelativeLengths,
  containerQueryLengthUnits, // Alias of `containerRelativeLengths`
} from 'css-units-list'
```
