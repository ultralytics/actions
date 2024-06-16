# url-or-path

[![Build Status][github_actions_badge]][github_actions_link]
[![Coverage][coveralls_badge]][coveralls_link]
[![Npm Version][package_version_badge]][package_link]
[![MIT License][license_badge]][license_link]

[github_actions_badge]: https://img.shields.io/github/workflow/status/fisker/url-or-path/CI/main?style=flat-square
[github_actions_link]: https://github.com/fisker/url-or-path/actions?query=branch%3Amain
[coveralls_badge]: https://img.shields.io/coveralls/github/fisker/url-or-path/main?style=flat-square
[coveralls_link]: https://coveralls.io/github/fisker/url-or-path?branch=main
[license_badge]: https://img.shields.io/npm/l/prettier-format.svg?style=flat-square
[license_link]: https://github.com/fisker/url-or-path/blob/main/license
[package_version_badge]: https://img.shields.io/npm/v/url-or-path.svg?style=flat-square
[package_link]: https://www.npmjs.com/package/url-or-path

> Convert between file URL and path.

## Install

```bash
yarn add url-or-path
```

## Usage

```js
import {toUrl, toPath} from 'url-or-path'

console.log(toUrl(urlOrPath))
//=> URL {/* ... */}

console.log(toPath(urlOrPath))
//=> 'path/to/file'
```

## API

### `toUrl(urlOrPath)`(alias `toURL`)

Type: `string | URL`

Returns a [`URL`](https://nodejs.org/dist/latest-v16.x/docs/api/url.html#url_class_url) object of given URL or path string.

### `toPath(urlOrPath)`

Type: `string | URL`

Returns path string of given URL or path string.

### `toDirectory(urlOrPath)`

Type: `string | URL`

Same as `toUrl`, but the result URL always ends with `/`.

### `isUrl(object)`

Check if `object` is a `URL` instance of `file://` string.

### `isUrlInstance(object)`

Check if `object` is a `URL` instance.

### `isUrlString(object)`

Check if `object` is a `file://` string
