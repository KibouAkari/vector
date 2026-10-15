const DOCUMENT_FORMATS = new Set(['pdf', 'docx']);

// The server JSON exporter produces XLSX only. It cannot fulfill a document request.
export function toolsForArtifactFormat(tools, requestedFormat) {
  if (!DOCUMENT_FORMATS.has(requestedFormat)) return tools;
  return tools.filter(tool => tool?.name !== 'artifact_create_from_server_json');
}

export function assertRequestedArtifactFormat(requestedFormat, actualFormat) {
  if (!requestedFormat) return;
  const actual = String(actualFormat || '').toLowerCase();
  if (actual !== requestedFormat) {
    throw new Error(
      `The user requested ${requestedFormat.toUpperCase()}. ` +
      `${actual ? actual.toUpperCase() : 'An unknown file format'} cannot fulfill this request. ` +
      'Use the requested format; never silently substitute another file type.'
    );
  }
}
