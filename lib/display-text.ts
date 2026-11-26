/** One source decoding boundary: preserve LF and escaped backslashes. */
export function displaySourceText(value: string): string {
  return value.replace(/(^|[^\\])\\n/g, "$1\n");
}
