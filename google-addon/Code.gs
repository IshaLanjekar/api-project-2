const API_BASE_URL_PROPERTY = 'SPAM_API_BASE_URL';
const USER_KEYWORDS_PROPERTY = 'SPAM_USER_KEYWORDS';
const MAIN_WEBSITE_URL_PROPERTY = 'SPAM_MAIN_WEBSITE_URL';
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
    'https://www.relume.io/app/project/P3198235_N9ubQWEUeJYt3MCAocflvWoO1S7G4A174fzr922cte0#mode=design'
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
    'https://www.relume.io/app/project/P3198235_N9ubQWEUeJYt3MCAocflvWoO1S7G4A174fzr922cte0#mode=design';

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

function _notify(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text))
    .build();
}
