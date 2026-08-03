const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');

const messagesFilePath = path.join(__dirname, '../data/messages.json');

/**
 * POST /api/contact
 * Handles contact / feedback form submissions
 */
router.post('/', (req, res) => {
  const { name, email, subject, message } = req.body;

  if (!name || !email || !message) {
    return res.status(400).json({
      success: false,
      message: '이름, 이메일, 문의 내용을 모두 입력해 주세요.'
    });
  }

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return res.status(400).json({
      success: false,
      message: '유효한 이메일 주소를 입력해 주세요.'
    });
  }

  let messages = [];
  try {
    if (fs.existsSync(messagesFilePath)) {
      messages = JSON.parse(fs.readFileSync(messagesFilePath, 'utf8'));
    }
  } catch (e) {
    messages = [];
  }

  const newMessage = {
    id: `msg-${Date.now()}`,
    name,
    email,
    subject: subject || '일반 문의',
    message,
    createdAt: new Date().toISOString()
  };

  messages.push(newMessage);
  try {
    fs.writeFileSync(messagesFilePath, JSON.stringify(messages, null, 2), 'utf8');
  } catch (e) {
    console.error('Failed to save message:', e);
  }

  console.log(`[CONTACT RECEIVED] From: ${name} (${email}), Subject: ${subject}`);

  res.json({
    success: true,
    message: '문의가 성공적으로 접수되었습니다. 담당자가 신속히 검토 후 답변드리겠습니다.'
  });
});

module.exports = router;
