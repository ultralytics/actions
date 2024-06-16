import {fileURLToPath, pathToFileURL} from 'node:url'

const isUrlInstance = (urlOrPath) => urlOrPath instanceof URL
const isUrlString = (urlOrPath) =>
  typeof urlOrPath === 'string' && urlOrPath.startsWith('file://')

const isUrl = (urlOrPath) => isUrlInstance(urlOrPath) || isUrlString(urlOrPath)

const toUrl = (urlOrPath) => {
  if (isUrlInstance(urlOrPath)) {
    return urlOrPath
  }

  if (isUrlString(urlOrPath)) {
    return new URL(urlOrPath)
  }

  return pathToFileURL(urlOrPath)
}

const toPath = (urlOrPath) =>
  isUrl(urlOrPath) ? fileURLToPath(urlOrPath) : urlOrPath

const addSlash = (url) =>
  url.href.endsWith('/') ? url : new URL(`${url.href}/`)

const toDirectory = (urlOrPath) => addSlash(toUrl(urlOrPath))

export {
  isUrl,
  isUrlInstance,
  isUrlString,
  toDirectory,
  toUrl,
  toUrl as toURL,
  toPath,
}
