# Gmail Add-on for Spam Filter API

This folder contains a Google Workspace Gmail Add-on that calls your Flask spam filter API.

## 1) Deploy your Flask API

Make sure your app is reachable over HTTPS and that this endpoint works:

- `POST /addon/predict`

Example request body:

```json
{ "text": "email content" }
```

Example response:

```json
{ "spam": 1, "label": "Spam", "confidence": 0.97 }
```

## 2) Create Apps Script project

1. Open https://script.google.com and create a new project.
2. Replace `Code.gs` with the file in this folder.
3. Replace `appsscript.json` with the file in this folder:
   - In Apps Script, enable **Project Settings > Show appsscript.json**.
4. Save the project.

## 3) Configure API URL in Script Properties

In Apps Script editor, run this snippet once from the editor:

```javascript
function setApiBaseUrl() {
  PropertiesService.getScriptProperties().setProperty(
    'SPAM_API_BASE_URL',
    'https://YOUR-DEPLOYED-API-DOMAIN'
  );
}
```

Replace with your real API URL and run `setApiBaseUrl`.

## 4) Configure the detailed analysis website

The **Go for Detailed Analysis** button opens your deployed website, not the local file in this workspace. If you update [index.html](../index.html), redeploy the website so the add-on can open the updated version.

In Apps Script editor, run this snippet once from the editor:

```javascript
function setMainWebsiteUrl() {
  PropertiesService.getScriptProperties().setProperty(
    'SPAM_MAIN_WEBSITE_URL',
    'https://ishalanjekar.github.io/api-project-2/index.html'
  );
}
```

If your published site URL is different, replace it with that URL.

## 5) Test in Gmail

1. Click **Deploy > Test deployments**.
2. Choose **Editor add-on** and install.
3. Open Gmail, open any email, and run **Analyze Current Email**.

## Notes

- This add-on reads subject and plain-text body from the open email.
- It sends that text to your Flask API for spam prediction.
- If your API host sleeps (free tier), first request may be slow.
