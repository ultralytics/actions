# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### [2.0.1](https://github.com/prettier/yaml-unist-parser/compare/v2.0.0...v2.0.1) (2022-10-14)


### Bug Fixes

* fix import/export path ([#289](https://github.com/prettier/yaml-unist-parser/issues/289)) ([5c41875](https://github.com/prettier/yaml-unist-parser/commit/5c4187537fbb96ed204b05798fb2fcf964c1cd75))

## [2.0.0](https://github.com/prettier/yaml-unist-parser/compare/v1.1.1...v2.0.0) (2022-10-14)


### ⚠ BREAKING CHANGES

* switch to esm (#288)
* drop support for Node.js < 14 (#285)

### Features

* switch to esm ([#288](https://github.com/prettier/yaml-unist-parser/issues/288)) ([a23343e](https://github.com/prettier/yaml-unist-parser/commit/a23343e717e599667180b19bd18c616bfcdd7167))
* treat "<<" as normal key but allow duplication ([#274](https://github.com/prettier/yaml-unist-parser/issues/274)) ([2fda6ef](https://github.com/prettier/yaml-unist-parser/commit/2fda6ef24eaaea2da1a14098b3cdf4a564021822))


### Bug Fixes

* **attach:** end comments for the first item in block mapping/sequence ([#276](https://github.com/prettier/yaml-unist-parser/issues/276)) ([92568ad](https://github.com/prettier/yaml-unist-parser/commit/92568ad6780f278bfd90a0aba3cb16e12a1fe03d))
* **attach:** end comments in flow collections ([#270](https://github.com/prettier/yaml-unist-parser/issues/270)) ([1346a27](https://github.com/prettier/yaml-unist-parser/commit/1346a279fdc0b3df436972dc3eebc7f5a0e4a766))
* no false positive for document head end marker position ([#272](https://github.com/prettier/yaml-unist-parser/issues/272)) ([4da66cb](https://github.com/prettier/yaml-unist-parser/commit/4da66cb1b9e6294d0501bddada7713eb00bd6e35))


* drop support for Node.js < 14 ([#285](https://github.com/prettier/yaml-unist-parser/issues/285)) ([ce6a042](https://github.com/prettier/yaml-unist-parser/commit/ce6a042703b32fa12f8718ac1682b3725cd94097))

<a name="1.3.1"></a>
## [1.3.1](https://github.com/ikatyang/yaml-unist-parser/compare/v1.3.0...v1.3.1) (2020-09-08)


### Bug Fixes

* **attach:** end comments for the first item in block mapping/sequence ([#276](https://github.com/ikatyang/yaml-unist-parser/issues/276)) ([92568ad](https://github.com/ikatyang/yaml-unist-parser/commit/92568ad))



<a name="1.3.0"></a>
# [1.3.0](https://github.com/ikatyang/yaml-unist-parser/compare/v1.2.1...v1.3.0) (2020-08-01)


### Features

* treat "<<" as normal key but allow duplication ([#274](https://github.com/ikatyang/yaml-unist-parser/issues/274)) ([2fda6ef](https://github.com/ikatyang/yaml-unist-parser/commit/2fda6ef))



<a name="1.2.1"></a>
## [1.2.1](https://github.com/ikatyang/yaml-unist-parser/compare/v1.2.0...v1.2.1) (2020-05-24)


### Bug Fixes

* no false positive for document head end marker position ([#272](https://github.com/ikatyang/yaml-unist-parser/issues/272)) ([4da66cb](https://github.com/ikatyang/yaml-unist-parser/commit/4da66cb))



<a name="1.2.0"></a>
# [1.2.0](https://github.com/ikatyang/yaml-unist-parser/compare/v1.1.1...v1.2.0) (2020-05-23)


### Bug Fixes

* **attach:** end comments in flow collections ([#270](https://github.com/ikatyang/yaml-unist-parser/issues/270)) ([1346a27](https://github.com/ikatyang/yaml-unist-parser/commit/1346a27))


### Chores

* **deps:** update dependency `yaml` to 1.10.0 ([#269](https://github.com/ikatyang/yaml-unist-parser/issues/269)) ([2cf5008](https://github.com/ikatyang/yaml-unist-parser/commit/2cf5008))



<a name="1.1.1"></a>
## [1.1.1](https://github.com/ikatyang/yaml-unist-parser/compare/v1.1.0...v1.1.1) (2019-10-09)


### Bug Fixes

* **deps:** update dependency `tslib` to 1.10.0 ([#227](https://github.com/ikatyang/yaml-unist-parser/issues/227)) ([6f88029](https://github.com/ikatyang/yaml-unist-parser/commit/6f88029))



<a name="1.1.0"></a>
# [1.1.0](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.1...v1.1.0) (2019-10-08)


### Features

* update `yaml` to 1.7.1 and move it to `dependencies` ([#225](https://github.com/ikatyang/yaml-unist-parser/issues/225)) ([df6412b](https://github.com/ikatyang/yaml-unist-parser/commit/df6412b))



<a name="1.0.1"></a>
## [1.0.1](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.0...v1.0.1) (2019-10-08)


### Chores

* `yaml@1.2.0+` is not supported in `yaml-unist-parser@1.0.x` ([207589e](https://github.com/ikatyang/yaml-unist-parser/commit/207589e))


<a name="1.0.0"></a>
# [1.0.0](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.0-rc.4...v1.0.0) (2018-11-15)


### Bug Fixes

* support CRLF ([f3801ca](https://github.com/ikatyang/yaml-unist-parser/commit/f3801ca))
* suppress offset errors ([470916c](https://github.com/ikatyang/yaml-unist-parser/commit/470916c))


### Chores

* upgrade yaml to v1 ([4830974](https://github.com/ikatyang/yaml-unist-parser/commit/4830974))


### BREAKING CHANGES

* require `yaml@^1.0.2`



<a name="1.0.0-rc.4"></a>
# [1.0.0-rc.4](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.0-rc.3...v1.0.0-rc.4) (2018-08-30)


### Bug Fixes

* enable merge (`<<`) parsing so that multiple `<<` won't be marked as duplicate keys ([#74](https://github.com/ikatyang/yaml-unist-parser/issues/74)) ([7a5b482](https://github.com/ikatyang/yaml-unist-parser/commit/7a5b482))


### Features

- transform AST from `yaml` AST+CST ([#82](https://github.com/ikatyang/yaml-unist-parser/issues/82)) ([2045635](https://github.com/ikatyang/yaml-unist-parser/commit/2045635))
  - `mappingKey` and `mappingValue` are now always presented in [`mappingItem`](https://github.com/ikatyang/yaml-unist-parser/blob/284fdf8d04aec5e58e186254056ec33357eebd10/src/types.ts#L173-L176)
  - `comment`s aren't presented in `children` anymore (moved to `*Comments?` fields)
  - attach `trailingComment` on `document` (`... #comment`)
  - attach `trailingComment` on `documentHead` (`--- #comment`)
  - `comment` between `blockValue` indicator and its value is now placed in [`indicatorComment`](https://github.com/ikatyang/yaml-unist-parser/blob/284fdf8d04aec5e58e186254056ec33357eebd10/src/types.ts#L143)

### BREAKING CHANGES

- remove some unnecessary `leadingComments`/`trailingComments` fields
- rename `trailingComments` with [`trailingComment`](https://github.com/ikatyang/yaml-unist-parser/blob/284fdf8d04aec5e58e186254056ec33357eebd10/src/types.ts#L48-L51) as it's only possible to be 0 or 1
- replace `shorthandTag`/`verbatimTag`/`nonSpecificTag` with [`tag`](https://github.com/ikatyang/yaml-unist-parser/blob/284fdf8d04aec5e58e186254056ec33357eebd10/src/types.ts#L101-L103)



<a name="1.0.0-rc.3"></a>
# [1.0.0-rc.3](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.0-rc.2...v1.0.0-rc.3) (2018-07-31)


### Bug Fixes

* **attach:** end comments in nested mapping ([#70](https://github.com/ikatyang/yaml-unist-parser/issues/70)) ([efc71fa](https://github.com/ikatyang/yaml-unist-parser/commit/efc71fa))



<a name="1.0.0-rc.2"></a>
# [1.0.0-rc.2](https://github.com/ikatyang/yaml-unist-parser/compare/v1.0.0-rc.1...v1.0.0-rc.2) (2018-07-17)


### Bug Fixes

* **attach:** no crash at mappingKey with null and comment ([#55](https://github.com/ikatyang/yaml-unist-parser/issues/55)) ([df3face](https://github.com/ikatyang/yaml-unist-parser/commit/df3face))
* **peerDeps:** require yaml@^1.0.0-rc.7 ([#61](https://github.com/ikatyang/yaml-unist-parser/issues/61)) ([6532413](https://github.com/ikatyang/yaml-unist-parser/commit/6532413))


### Features

* attach end comments ([#60](https://github.com/ikatyang/yaml-unist-parser/issues/60)) ([9a29f4a](https://github.com/ikatyang/yaml-unist-parser/commit/9a29f4a))
