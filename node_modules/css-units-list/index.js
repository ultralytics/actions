// https://www.w3.org/TR/css-values-4/#font-relative-lengths
const fontRelativeLengths = ['em', 'ex', 'cap', 'ch', 'ic', 'lh'].flatMap(
  (unit) => [unit, `r${unit}`],
)

// https://www.w3.org/TR/css-values-4/#viewport-relative-lengths
const viewportPercentageLengths = [
  'vw',
  'vh',
  'vi',
  'vb',
  'vmin',
  'vmax',
].flatMap((unit) => [unit, `s${unit}`, `l${unit}`, `d${unit}`])

// https://www.w3.org/TR/css-values-4/#relative-lengths
const relativeLengths = [...fontRelativeLengths, ...viewportPercentageLengths]

// https://www.w3.org/TR/css-values-4/#absolute-lengths
const absoluteLengths = ['cm', 'mm', 'Q', 'in', 'pt', 'pc', 'px']

// https://www.w3.org/TR/css-values-4/#lengths
const distanceUnits = [...relativeLengths, ...absoluteLengths]

// https://www.w3.org/TR/css-values-4/#angles
const angleUnits = ['deg', 'grad', 'rad', 'turn']

// https://www.w3.org/TR/css-values-4/#time
const durationUnits = ['s', 'ms']

// https://www.w3.org/TR/css-values-4/#frequency
const frequencyUnits = ['Hz', 'kHz']

// https://www.w3.org/TR/css-values-4/#resolution
const resolutionUnits = ['dpi', 'dpcm', 'dppx', 'x']

// https://www.w3.org/TR/css-values-4/#other-units
const otherQuantities = [
  ...angleUnits,
  ...durationUnits,
  ...frequencyUnits,
  ...resolutionUnits,
]

// https://drafts.csswg.org/css-contain-3/#container-lengths
const containerRelativeLengths = ['cqw', 'cqh', 'cqi', 'cqb', 'cqmin', 'cqmax']

const allUnits = [
  ...distanceUnits,
  ...otherQuantities,
  ...containerRelativeLengths,
]

export default allUnits
export {
  fontRelativeLengths,
  viewportPercentageLengths,
  relativeLengths,
  absoluteLengths,
  angleUnits,
  durationUnits,
  frequencyUnits,
  resolutionUnits,
  containerRelativeLengths,
  containerRelativeLengths as containerQueryLengthUnits,
}
