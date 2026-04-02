const API_BASE_URL_PROPERTY = 'SPAM_API_BASE_URL';
const USER_KEYWORDS_PROPERTY = 'SPAM_USER_KEYWORDS';
const MAIN_WEBSITE_URL_PROPERTY = 'SPAM_MAIN_WEBSITE_URL';
const LAST_ANALYSIS_RESULT_PROPERTY = 'SPAM_LAST_ANALYSIS_RESULT';
const MAX_TEXT_LENGTH = 4000;

function setApiBaseUrl() {
  PropertiesService.getScriptProperties().setProperty(
    API_BASE_URL_PROPERTY,
    'https://email-spam-filter-api.onrender.com'
  );
}

function setMainWebsiteUrl() {
  PropertiesService.getScriptProperties().setProperty(
    MAIN_WEBSITE_URL_PROPERTY,
    'https://ishalanjekar.github.io/api-project-2/index.html#analysis'
  );
}

function buildHomeCard() {
  const currentKeywords = _getUserKeywords();
  const section = CardService.newCardSection()
    .addWidget(
      CardService.newTextParagraph().setText('Set your keywords')
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName('keywordsInput')
        .setTitle('Keywords (comma-separated)')
        .setHint('Example: meeting, college, project')
        .setValue(currentKeywords.join(', '))
    )
    .addWidget(
      CardService.newTextButton()
        .setText('+ Add')
        .setOnClickAction(CardService.newAction().setFunctionName('saveKeywords'))
    )
    .addWidget(
      CardService.newTextButton()
        .setText('Analyze Current Email')
        .setOnClickAction(CardService.newAction().setFunctionName('analyzeCurrentEmail'))
    )
    .addWidget(
      CardService.newTextButton()
        .setText('Continue - Fetch & Analyze Emails')
        .setOnClickAction(CardService.newAction().setFunctionName('fetchAndAnalyzeInboxEmails'))
    );

  return [
    CardService.newCardBuilder()
      .setHeader(CardService.newCardHeader().setTitle('Spam Filter Assistant'))
      .addSection(section)
      .build()
  ];
}

function buildContextCard(e) {
  return buildHomeCard(e);
}

function analyzeCurrentEmail(e) {
  const messageId = _extractMessageId(e);
  if (!messageId) {
    return _notify('Could not detect current message. Open an email and retry.');
  }

  const message = GmailApp.getMessageById(messageId);
  if (!message) {
    return _notify('Message not found.');
  }

  const subject = message.getSubject() || '';
  const plainBody = message.getPlainBody() || '';
  const trimmedBody = plainBody.slice(0, MAX_TEXT_LENGTH);
  const payload = {
    text: [subject, trimmedBody].join('\n\n'),
    keywords: _getUserKeywords()
  };

  try {
    const result = _callSpamApi(payload);
    PropertiesService.getUserProperties().setProperty(
      LAST_ANALYSIS_RESULT_PROPERTY,
      JSON.stringify(result)
    );
    const spamValue = Number(result.spam) === 1;
    const label = result.label || (spamValue ? 'Spam' : 'Not Spam');

    let details = '<b>Classification:</b> ' + label;
    if (typeof result.confidence === 'number') {
      details += '<br/><b>Confidence:</b> ' + Math.round(result.confidence * 100) + '%';
    }
    if (result.keyword_override) {
      details += '<br/><b>Keyword Rule:</b> Applied';
    }
    if (result.keyword_matches && result.keyword_matches.length) {
      details += '<br/><b>Matched Keywords:</b> ' + result.keyword_matches.join(', ');
    }

    const section = CardService.newCardSection()
      .addWidget(CardService.newTextParagraph().setText(details))
      .addWidget(
        CardService.newTextParagraph().setText(
          spamValue
            ? 'Recommendation: Move this email to Spam and avoid clicking links.'
            : 'Recommendation: This email looks safe based on the model output.'
        )
      )
      .addWidget(
        CardService.newTextButton()
          .setText('Go for Detailed Analysis')
          .setOpenLink(CardService.newOpenLink().setUrl(_buildDetailedAnalysisUrl(result)))
      );

    if (plainBody.length > MAX_TEXT_LENGTH) {
      section.addWidget(
        CardService.newTextParagraph().setText(
          'Note: Only the first ' + MAX_TEXT_LENGTH + ' characters were analyzed for speed.'
        )
      );
    }

    const card = CardService.newCardBuilder()
      .setHeader(CardService.newCardHeader().setTitle('Spam Check Result'))
      .addSection(section)
      .build();

    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(card))
      .build();
  } catch (err) {
    return _notify(
      'API call timed out or failed. Retry in 10-20 seconds (Render cold start) or open a shorter email.'
    );
  }
}

function showDetailedAnalysis() {
  const raw = PropertiesService.getUserProperties().getProperty(LAST_ANALYSIS_RESULT_PROPERTY);
  if (!raw) {
    return _notify('Run Analyze Current Email first to generate detailed analysis.');
  }

  try {
    const result = JSON.parse(raw);
    const card = _buildDetailedAnalysisCard(result);
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(card))
      .build();
  } catch (err) {
    return _notify('Could not load detailed analysis. Please analyze the email again.');
  }
}

function fetchInboxEmails(e) {
  try {
    const threads = GmailApp.search('in:inbox', 0, 30);
    if (!threads.length) {
      return _notify('No inbox emails found.');
    }

    const section = CardService.newCardSection()
      .addWidget(
        CardService.newTextParagraph().setText(
          '<b>Latest 30 Inbox Emails</b><br/>Showing the newest inbox threads from your own Gmail box.'
        )
      );

    threads.forEach(function (thread, index) {
      const messages = thread.getMessages();
      const message = messages[messages.length - 1];
      const subject = (message.getSubject() || '(No subject)').substring(0, 120);
      const from = (message.getFrom() || '').substring(0, 80);
      const snippet = (message.getPlainBody() || '').replace(/\s+/g, ' ').substring(0, 140);

      section.addWidget(
        CardService.newTextParagraph().setText(
          '<b>' + (index + 1) + '.</b> ' + subject + '<br/>' + from + '<br/>' + snippet
        )
      );
    });

    const card = CardService.newCardBuilder()
      .setHeader(CardService.newCardHeader().setTitle('Inbox Snapshot'))
      .addSection(section)
      .build();

    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(card))
      .build();
  } catch (err) {
    return _notify('Could not fetch inbox emails: ' + err.message);
  }
}

function fetchAndAnalyzeInboxEmails(e) {
  try {
    const threads = GmailApp.search('in:inbox', 0, 30);
    if (!threads.length) {
      return _notify('No inbox emails found.');
    }

    const items = threads.map(function (thread) {
      const message = thread.getMessages()[thread.getMessageCount() - 1];
      const subject = (message.getSubject() || '(No subject)').substring(0, 160);
      const plainBody = message.getPlainBody() || '';
      const trimmedBody = plainBody.slice(0, MAX_TEXT_LENGTH);
      return {
        subject: subject,
        text: [subject, trimmedBody].join('\n\n')
      };
    });

    const batchResult = _callSpamApiBatch({
      items: items,
      keywords: _getUserKeywords()
    });

    const summary = batchResult.summary || {};
    const total = Number(summary.total || items.length);
    const spamCount = Number(summary.spam || 0);
    const safeCount = Number(summary.safe || 0);

    const section = CardService.newCardSection()
      .addWidget(
        CardService.newTextParagraph().setText(
          '<b>Inbox Analysis Summary</b><br/>Latest inbox emails analyzed from your Gmail box.'
        )
      )
      .addWidget(
        CardService.newTextParagraph().setText(
          '<b>Total analyzed:</b> ' + total + '<br/>' +
          '<b>Spam:</b> ' + spamCount + '<br/>' +
          '<b>Safe:</b> ' + safeCount
        )
      );

    const card = CardService.newCardBuilder()
      .setHeader(CardService.newCardHeader().setTitle('Inbox Analysis'))
      .addSection(section)
      .build();

    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(card))
      .build();
  } catch (err) {
    return _notify('Could not analyze inbox emails: ' + err.message);
  }
}

function _callSpamApiBatch(payload) {
  const baseUrl = PropertiesService.getScriptProperties().getProperty(API_BASE_URL_PROPERTY);
  if (!baseUrl) {
    throw new Error('Missing script property SPAM_API_BASE_URL');
  }

  const response = UrlFetchApp.fetch(baseUrl.replace(/\/$/, '') + '/addon/predict-batch', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const status = response.getResponseCode();
  const body = response.getContentText();

  if (status < 200 || status >= 300) {
    throw new Error('HTTP ' + status + ': ' + body);
  }

  return JSON.parse(body);
}

function saveKeywords(e) {
  const rawInput = _getFormInputValue(e, 'keywordsInput');
  const parsed = _parseKeywords(rawInput);

  PropertiesService.getUserProperties().setProperty(
    USER_KEYWORDS_PROPERTY,
    JSON.stringify(parsed)
  );

  const card = buildHomeCard()[0];
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(card))
    .setNotification(
      CardService.newNotification().setText('Keywords saved: ' + (parsed.join(', ') || 'none'))
    )
    .build();
}

function _callSpamApi(payload) {
  const baseUrl = PropertiesService.getScriptProperties().getProperty(API_BASE_URL_PROPERTY);
  if (!baseUrl) {
    throw new Error('Missing script property SPAM_API_BASE_URL');
  }

  const response = UrlFetchApp.fetch(baseUrl.replace(/\/$/, '') + '/addon/predict', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const status = response.getResponseCode();
  const body = response.getContentText();

  if (status < 200 || status >= 300) {
    throw new Error('HTTP ' + status + ': ' + body);
  }

  return JSON.parse(body);
}

function _extractMessageId(e) {
  if (e && e.gmail && e.gmail.messageId) {
    return e.gmail.messageId;
  }
  return null;
}

function _getUserKeywords() {
  const raw = PropertiesService.getUserProperties().getProperty(USER_KEYWORDS_PROPERTY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(Boolean);
  } catch (err) {
    return [];
  }
}

function _parseKeywords(raw) {
  if (!raw) {
    return [];
  }

  const keywords = raw
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  return [...new Set(keywords)].slice(0, 30);
}

function _getFormInputValue(e, fieldName) {
  const fields = e && e.commonEventObject && e.commonEventObject.formInputs;
  if (!fields || !fields[fieldName]) {
    return '';
  }

  const input = fields[fieldName];
  const values = input.stringInputs && input.stringInputs.value;
  return values && values.length ? values[0] : '';
}

function _buildDetailedAnalysisUrl(result) {
  const baseUrl =
    PropertiesService.getScriptProperties().getProperty(MAIN_WEBSITE_URL_PROPERTY) ||
    'https://ishalanjekar.github.io/api-project-2/index.html#analysis';

  const params = [];

  if (result && result.label) {
    params.push('label=' + encodeURIComponent(result.label));
  }
  if (result && typeof result.confidence === 'number') {
    params.push('confidence=' + encodeURIComponent(Math.round(result.confidence * 100)));
  }
  if (result && result.keyword_matches && result.keyword_matches.length) {
    params.push('keywords=' + encodeURIComponent(result.keyword_matches.join(',')));
  }

  const hashIndex = baseUrl.indexOf('#');
  const baseWithoutHash = hashIndex >= 0 ? baseUrl.slice(0, hashIndex) : baseUrl;
  const hashPart = hashIndex >= 0 ? baseUrl.slice(hashIndex) : '';
  const separator = baseWithoutHash.indexOf('?') >= 0 ? '&' : '?';

  if (!params.length) {
    return baseUrl;
  }

  return baseWithoutHash + separator + params.join('&') + hashPart;
}

function _buildDetailedAnalysisCard(result) {
  const spamValue = Number(result && result.spam) === 1;
  const label = (result && result.label) || (spamValue ? 'Spam' : 'Not Spam');
  const confidenceValue =
    result && typeof result.confidence === 'number'
      ? Math.round(result.confidence * 100) + '%'
      : 'N/A';
  const matchedKeywords = result && result.keyword_matches && result.keyword_matches.length
    ? result.keyword_matches.join(', ')
    : 'None';

  const section = CardService.newCardSection()
    .addWidget(
      CardService.newTextParagraph().setText(
        '<b>Classification:</b> ' + label + '<br/>' +
        '<b>Confidence:</b> ' + confidenceValue + '<br/>' +
        '<b>Matched Keywords:</b> ' + matchedKeywords
      )
    )
    .addWidget(
      CardService.newTextParagraph().setText(
        spamValue
          ? 'Detailed view: this email looks risky. Avoid links or attachments and review the sender carefully.'
          : 'Detailed view: this email looks safe based on the model output and your trusted keywords.'
      )
    )
    .addWidget(
      CardService.newTextParagraph().setText(
        '<b>What to do next:</b><br/>' +
        (spamValue
          ? 'Mark as spam if the sender is unknown, then ignore future similar emails.'
          : 'Keep it in inbox and continue using your trusted keywords list.')
      )
    );

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Detailed Analysis'))
    .addSection(section)
    .build();
}

function _notify(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text))
    .build();
}
