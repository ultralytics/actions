export default function sdbm(string) {
	let hash = 0;

	for (let i = 0; i < string.length; i++) {
		hash = string.charCodeAt(i) + (hash << 6) + (hash << 16) - hash;
	}

	// Convert it to an unsigned 32-bit integer.
	return hash >>> 0;
}
