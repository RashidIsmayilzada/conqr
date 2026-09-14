/**
 * ConQR check-in webhook.
 *
 * Paste this into: your Google Sheet -> Extensions -> Apps Script,
 * replace SHARED_SECRET below with your own secret, then deploy it as a
 * Web App (Deploy -> New deployment -> type: Web app, execute as: Me,
 * who has access: Anyone with the link). Copy the resulting /exec URL
 * into SHEET_CHECKIN_URL in your .env, and put the same secret into
 * SHEET_CHECKIN_SECRET.
 *
 * When a guest is scanned at the door, ConQR calls this Web App with the
 * guest's email + name. This script finds the matching row in your Form
 * Responses sheet and fills in "Checked In" / "Checked In At" columns
 * (creating those columns automatically the first time it runs).
 */

var SHARED_SECRET = "REPLACE_WITH_YOUR_SECRET";
var SHEET_NAME = "Form Responses 1"; // change if your responses tab has a different name
var EMAIL_COLUMN_HEADER = "Email"; // must match your sheet's header text exactly
var NAME_COLUMN_HEADER = "Ad Soyad"; // used only to disambiguate duplicate emails
var CHECKED_IN_HEADER = "Checked In";
var CHECKED_AT_HEADER = "Checked In At";

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    if (payload.secret !== SHARED_SECRET) {
      return jsonResponse({ ok: false, error: "unauthorized" });
    }

    var email = String(payload.email || "").trim().toLowerCase();
    var fullName = String(payload.full_name || "").trim().toLowerCase();
    var checkedAt = payload.checked_in_at || new Date().toISOString();

    if (!email) {
      return jsonResponse({ ok: false, error: "missing email" });
    }

    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
    if (!sheet) {
      return jsonResponse({ ok: false, error: "sheet not found: " + SHEET_NAME });
    }

    var data = sheet.getDataRange().getValues();
    if (data.length < 1) {
      return jsonResponse({ ok: false, error: "sheet is empty" });
    }
    var headers = data[0].map(function (h) { return String(h).trim(); });

    var emailCol = headers.indexOf(EMAIL_COLUMN_HEADER);
    var nameCol = headers.indexOf(NAME_COLUMN_HEADER);
    if (emailCol === -1) {
      return jsonResponse({ ok: false, error: "email column not found: " + EMAIL_COLUMN_HEADER });
    }

    var checkedCol = headers.indexOf(CHECKED_IN_HEADER);
    if (checkedCol === -1) {
      sheet.getRange(1, headers.length + 1).setValue(CHECKED_IN_HEADER);
      checkedCol = headers.length;
      headers.push(CHECKED_IN_HEADER);
    }
    var checkedAtCol = headers.indexOf(CHECKED_AT_HEADER);
    if (checkedAtCol === -1) {
      sheet.getRange(1, headers.length + 1).setValue(CHECKED_AT_HEADER);
      checkedAtCol = headers.length;
      headers.push(CHECKED_AT_HEADER);
    }

    var matchedRow = -1;
    for (var r = 1; r < data.length; r += 1) {
      var rowEmail = String(data[r][emailCol] || "").trim().toLowerCase();
      var rowName = nameCol > -1 ? String(data[r][nameCol] || "").trim().toLowerCase() : "";
      var alreadyChecked = String(data[r][checkedCol] || "").trim().toLowerCase() === "yes";
      if (rowEmail === email && (!fullName || !rowName || rowName === fullName) && !alreadyChecked) {
        matchedRow = r;
        break;
      }
    }

    if (matchedRow === -1) {
      for (var r2 = 1; r2 < data.length; r2 += 1) {
        var rowEmail2 = String(data[r2][emailCol] || "").trim().toLowerCase();
        if (rowEmail2 === email) {
          matchedRow = r2;
          break;
        }
      }
    }

    if (matchedRow === -1) {
      return jsonResponse({ ok: false, error: "no matching row for " + email });
    }

    var sheetRow = matchedRow + 1; // convert back to 1-indexed sheet row
    sheet.getRange(sheetRow, checkedCol + 1).setValue("yes");
    sheet.getRange(sheetRow, checkedAtCol + 1).setValue(checkedAt);

    return jsonResponse({ ok: true, row: sheetRow });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err) });
  }
}

function jsonResponse(obj) {
  var output = ContentService.createTextOutput(JSON.stringify(obj));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}
