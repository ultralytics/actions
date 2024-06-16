# vnopts

[![npm](https://img.shields.io/npm/v/vnopts.svg)](https://www.npmjs.com/package/vnopts)
[![build](https://img.shields.io/github/actions/workflow/status/ikatyang/vnopts/test.yml)](https://github.com/ikatyang/vnopts/actions?query=branch%3Amaster)

validate and normalize options

[Changelog](https://github.com/ikatyang/vnopts/blob/master/CHANGELOG.md)

## Install

```sh
npm install vnopts
```

## Usage

```js
import * as vnopts from 'vnopts'

const schemas = [
  vnopts.ChoiceSchema.create({
    name: 'parser',
    choices: ['babylon', 'flow', 'typescript'],
  }),
  vnopts.BooleanSchema.create({
    name: 'useFlowParser',
    deprecated: true,
    redirect: value =>
      !value ? undefined : { to: { key: 'parser', value: 'flow' } },
  }),
]

vnopts.normalize({ useFlowParser: true }, schemas)
//=> { parser: "flow" }
// warning: `useFlowParser` is deprecated, we now treat it as `{ parser: "flow" }`.

vnopts.normalize({ parser: 'none' }, schemas)
//=> error: Invalid `parser` value. Expected `"babylon", "flow" or "typescript"`, but received `"none"`.

vnopts.normalize({ parserr: 'typescript' }, schemas)
//=> {}
// warning: Ignored unknown option `{ parserr: "typescript" }`. Did you mean `parser`?
```

## API

### Normalizer

```ts
/** a shortcut for `new Normalizer(...).normalize(...)` */
function normalize(
  options: object,
  schemas: Schema[],
  opts?: NormalizerOptions,
): object
```

```ts
class Normalizer {
  constructor(schemas: Schema[], opts?: NormalizerOptions)
  /** normalize the options based on schemas */
  normalize(options: object): object
  /** clear the deprecation warning history so as to show the same warning again */
  cleanHistory(): void
}
```

```ts
interface NormalizerOptions {
  logger?: Logger | false
  loggerPrintWidth?: number
  descriptor?: Descriptor
  unknown?: UnknownHandler
  invalid?: InvalidHandler
  deprecated?: DeprecatedHandler
  missing?: IdentifyMissing
  required?: IdentifyRequired
  preprocess?: (options: Options, utils: Utils) => Options
  postprocess?: (
    options: Options,
    utils: Utils,
  ) => typeof VALUE_UNCHANGED | { delete?: string[]; override?: Options }
}
```

#### Logger

Defaults to `console`.

```ts
interface Logger {
  warn(message: string): void
}
```

#### Descriptor

Defaults to [`apiDescriptor`](https://github.com/ikatyang/vnopts/blob/master/src/descriptors/api.ts).

```ts
interface Descriptor {
  key: (key: string) => string
  value: (value: any) => string
  pair: (pair: { key: string; value: any }) => string
}
```

#### UnknownHandler

Defaults to [`levenUnknownHandler`](https://github.com/ikatyang/vnopts/blob/master/src/handlers/unknown/leven.ts).

```ts
type UnknownHandler = (key: string, value: any, utils: Utils) => void | object
```

The returned object will be merged into the output object (and validate its value if the key is known).

#### InvalidHandler

Defaults to [`commonInvalidHandler`](https://github.com/ikatyang/vnopts/blob/master/src/handlers/invalid/common.ts).

```ts
type InvalidHandler = (
  key: string,
  value: OptionValue,
  utils: Utils,
) => string | Error
```

Returns an error message or the error itself.

#### DeprecatedHandler

Defaults to [`commonDeprecatedHandler`](https://github.com/ikatyang/vnopts/blob/master/src/handlers/deprecated/common.ts).

```ts
type DeprecatedHandler = (
  keyOrPair: string | { key: string; value: any },
  redirectToKeyOrPair: undefined | string | { key: string; value: any },
  utils: Utils,
) => string
```

Returns a deprecation warning.

#### IdentifyMissing

Defaults to `() => false`.

```ts
type IdentifyMissing = (key: string, options: Options) => boolean
```

Returns a boolean to indicate if `key` is _missing_ in `options`.
(`!(key in options)` is always considered missing.)

#### IdentifyRequired

Defaults to `() => false`.

```ts
type IdentifyRequired = (key: string) => boolean
```

Returns a boolean to indicate if `key` is required in the output.

### Schemas

#### AnySchema

```ts
interface AnySchemaParameters extends SchemaHandlers {
  name: string
}
```

```js
const schemas = [vnopts.AnySchema.create({ name: 'any' })]

vnopts.normalize({ any: 'hello world' }, schemas)
//=> { any: "hello world" }

vnopts.normalize({ unknown: 'hello world' }, schemas)
//=> {}
// warning: Ignored unknown option `{ unknown: "hello world" }`.
```

#### BooleanSchema

```ts
interface BooleanSchemaParameters extends SchemaHandlers {
  name: string
}
```

```js
const schemas = [vnopts.BooleanSchema.create({ name: 'bool' })]

vnopts.normalize({ bool: true }, schemas)
//=> { bool: true }

vnopts.normalize({ bool: 'hello world' }, schemas)
// error: Invalid `bool` value. Expected `true or false`, but received `"hello world"`.
```

#### NumberSchema

```ts
interface NumberSchemaParameters extends SchemaHandlers {
  name: string
}
```

```js
const schemas = [vnopts.NumberSchema.create({ name: 'num' })]

vnopts.normalize({ num: 1 }, schemas)
//=> { num: 1 }

vnopts.normalize({ num: null }, schemas)
// error: Invalid `num` value. Expected `a number`, but received `null`.
```

#### IntegerSchema

```ts
interface IntegerSchemaParameters extends SchemaHandlers {
  name: string
}
```

```js
const schemas = [vnopts.IntegerSchema.create({ name: 'int' })]

vnopts.normalize({ int: 1 }, schemas)
//=> { int: 1 }

vnopts.normalize({ int: 1.5 }, schemas)
// error: Invalid `int` value. Expected `an integer`, but received `1.5`.
```

#### StringSchema

```ts
interface StringSchemaParameters extends SchemaHandlers {
  name: string
}
```

```js
const schemas = [vnopts.StringSchema.create({ name: 'str' })]

vnopts.normalize({ str: 'hi' }, schemas)
//=> { str: "hi" }

vnopts.normalize({ str: true }, schemas)
// error: Invalid `str` value. Expected `a string`, but received `true`.
```

#### ChoiceSchema

```ts
interface ChoiceSchemaParameters extends SchemaHandlers {
  name: string
  choices: Array<
    | undefined
    | null
    | boolean
    | number
    | string
    | {
        value: undefined | null | boolean | number | string
        deprecated?: boolean
        hidden?: boolean // do not show this value in `expected`
        redirect?: /* key */ string | { key: string; value: any }
        forward?: /* key */ string | { key: string; value: any }
      }
  >
}
```

```js
const schemas = [
  vnopts.ChoiceSchema.create({ name: 'choice', choices: [2, false, 'hey'] }),
]

vnopts.normalize({ choice: 2 }, schemas)
//=> { choice: 2 }

vnopts.normalize({ choice: true }, schemas)
// error: Invalid `choice` value. Expected `false, 2 or "hey"`, but received `true`.
```

#### AliasSchema

`AliasSchema` validates values using the validator from the source schema and redirects all the value to the source key.

```ts
interface AliasSchemaParameters extends SchemaHandlers {
  name: string
  /** the name of the source schema */
  sourceName: string
}
```

```js
const schemas = [
  vnopts.BooleanSchema.create({ name: 'source' }),
  vnopts.AliasSchema.create({ name: 'alias', sourceName: 'source' }),
]

vnopts.normalize({ alias: true }, schemas)
//=> { source: true }

vnopts.normalize({ alias: 'invalid' }, schemas)
//=> error: Invalid `alias` value. Expected `true or false`, but received `"invalid"`.
```

#### ArraySchema

`AliasSchema` validates values using the validator from the source schema and redirects all the value to the source key.

```ts
interface ArraySchemaParameters extends SchemaHandlers {
  /** defaults to valueSchema's name */
  name?: string
  valueSchema: Schema
}
```

```js
const schemas = [
  vnopts.ArraySchema.create({
    valueSchema: vnopts.ChoiceSchema.create({
      name: 'choices',
      choices: [1, true, 'foo'],
    }),
  }),
]

vnopts.normalize({ choices: [1, 'foo'] }, schemas)
//=> { choices: [1, "foo"] }

vnopts.normalize({ choices: 1 }, schemas)
//=> error: Invalid `choices` value. Expected `an array of true, 1 or "foo"`, but received `1`.
```

### Handlers

Every schema has its own handlers but you can still override/extend them.

```ts
interface SchemaHandlers {
  default?: SchemaDefaultHandler
  expected?: SchemaExpectedHandler
  validate?: SchemaValidateHandler
  deprecated?: SchemaDeprecateHandler
  forward?: SchemaForwardHandler
  redirect?: SchemaRedirectHandler
  overlap?: SchemaOverlapHandler
  preprocess?: SchemaPreprocessHandler
  postprocess?: SchemaPostprocessHandler
}
```

#### default

```ts
type SchemaDefaultHandler =
  | DefaultResult
  | ((schema: Schema, utils: Utils) => DefaultResult)

type DefaultResult = undefined | { value?: any }
```

`undefined` represents no default value,
default values are wrapped in an object's `value` field
to avoid the ambiguity between missing and `undefined`.

#### expected

```ts
type SchemaExpectedHandler =
  | ExpectedResult
  | ((schema: Schema, utils: Utils) => ExpectedResult)

type ExpectedResult =
  | string
  | { text: string }
  | {
      text?: string
      list: {
        title: string
        values: ExpectedResult[]
      }
    }
```

Returns the description for the expected value in the form of text and/or list.
For example the following `ExpectedResult`:

```json
{
  "list": {
    "title": "one of the following values",
    "values": ["foo", "bar", "baz"]
  }
}
```

will produce the following message in `commonInvalidHandler`:

```
Invalid `<key>` value. Expected `one of the following values`, but received `<value>`.
- `"foo"`
- `"bar"`
- `"baz"`
```

If both `text` and `list` are returned,
`text` will be chosen if its width is the minimum one or its width is less than `loggerPrintWidth`,
otherwise `list`.

#### validate

```ts
type SchemaValidateHandler =
  | ValidateResult
  | ((value: unknown, schema: Schema, utils: Utils) => ValidateResult)

type ValidateResult = boolean | { value: unknown }
```

Returns a boolean represents if the entire value is valid,
or put the invalid value in an object's `value` field if only part of the value is invalid,
this is useful for collection schema like `ArraySchema`.

#### deprecated

```ts
type SchemaDeprecatedHandler =
  | DeprecatedResult
  | ((value: unknown, schema: Schema, utils: Utils) => DeprecatedResult)

type DeprecatedResult = boolean | { value: any } | Array<{ value: any }>
```

Returns `true` if the entire key is deprecated, `false` if it's not deprecated,
or (an array of) an object with `value` field if only part of the value is deprecated,
one object corresponds to one deprecation warning.

#### forward

```ts
type SchemaForwardHandler =
  | ForwardResult
  | ((value: any, schema: Schema, utils: Utils) => ForwardResult)

type TransferTo = /* key */ string | { key: string; value: any }
type TransferResult = TransferTo | { from?: /* value */ any; to: TransferTo }
type ForwardResult = undefined | TransferResult | Array<TransferResult>
```

Returns a key or a key-value pair if the entire value needs to be forwarded there,
or (an array of) an object with `from`/`to` field if only part of the value needs to be forwarded.

#### redirect

```ts
type SchemaRedirectHandler =
  | RedirectResult
  | ((value: any, schema: Schema, utils: Utils) => RedirectResult)

type RedirectResult =
  | ForwardResult
  | {
      remain?: any
      redirect: ForwardResult
    }
```

Similar to `forward` but returns an object with `remain`/`redirect` field if not the entire value needs to be redirected.

#### overlap

```ts
type SchemaOverlapHandler = (
  currentValue: any,
  newValue: any,
  schema: Schema,
  utils: Utils,
) => any
```

Describes what should the normalizer do if there're multiple values assigned to the same key.

#### preprocess

```ts
type SchemaPreprocessHandler = (
  value: unknown,
  schema: Schema,
  utils: Utils,
) => unknown
```

The preprocess before passing into the validator.

#### postprocess

```ts
type SchemaPostprocessHandler = (
  value: unknown,
  schema: Schema,
  utils: Utils,
) => unknown
```

The postprocess after normalization.

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
