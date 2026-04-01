const API_BASE_URL_PROPERTY = 'SPAM_API_BASE_URL';
const MAX_TEXT_LENGTH = 4000;

function setApiBaseUrl() {
  PropertiesService.getScriptProperties().setProperty(
    API_BASE_URL_PROPERTY,
    'https://email-spam-filter-api.onrender.com'
  );
}

function buildHomeCard() {
  const section = CardService.newCardSection()
    .addWidget(
      CardService.newTextParagraph().setText(
        'Spam Filter Assistant is ready. Open an email and click Analyze Current Email.'
      )
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
    text: [subject, trimmedBody].join('\n\n')
  };

  try {
    const result = _callSpamApi(payload);
    const spamValue = Number(result.spam) === 1;
    const label = result.label || (spamValue ? 'Spam' : 'Not Spam');

    let details = '<b>Classification:</b> ' + label;
    if (typeof result.confidence === 'number') {
      details += '<br/><b>Confidence:</b> ' + Math.round(result.confidence * 100) + '%';
    }

    const section = CardService.newCardSection()
      .addWidget(CardService.newTextParagraph().setText(details))
      .addWidget(
        CardService.newTextParagraph().setText(
          spamValue
            ? 'Recommendation: Move this email to Spam and avoid clicking links.'
            : 'Recommendation: This email looks safe based on the model output.'
        )
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

function _notify(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text))
    .build();
}
