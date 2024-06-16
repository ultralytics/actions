/**
[SDBM](http://www.cse.yorku.ca/~oz/hash.html#sdbm) non-cryptographic hash function.

@returns The hash as a positive integer.

@example
```
import sdbm from 'sdbm';

sdbm('🦄🌈');
//=> 4053542802
```
*/
export default function sfbm(string: string): number;
