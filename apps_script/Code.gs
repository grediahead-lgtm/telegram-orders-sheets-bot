/**
 * Google Apps Script web app: appends an order row to the active sheet.
 * Setup: Extensions > Apps Script, paste this file, set Script property ORDER_SECRET
 * (Project settings > Script properties), then Deploy > New deployment > Web app
 * (Execute as: Me, Who has access: Anyone). Put the /exec URL in config.json.
 * NOTE: this script was written for the example and is not tested against a live Google account here.
 */
var HEADERS = ['created_at', 'order_id', 'customer', 'username', 'item', 'quantity', 'contact', 'comment', 'photo_file_id'];

function doPost(e) {
  var out = function (obj) {
    return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
  };
  try {
    var data = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('ORDER_SECRET');
    if (!secret || data.secret !== secret) return out({ ok: false, error: 'forbidden' });
    var sheet = SpreadsheetApp.getActiveSheet();
    if (sheet.getLastRow() === 0) sheet.appendRow(HEADERS);
    sheet.appendRow(HEADERS.map(function (h) { return String(data[h] || '').slice(0, 500); }));
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: 'bad request' });
  }
}
