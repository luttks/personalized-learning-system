const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  // Login
  await page.goto('http://localhost:5173/login');
  await page.fill('input[type="email"]', 'student@example.com');
  await page.fill('input[type="password"]', 'student123');
  await page.click('button[type="submit"]');
  
  // Wait for login to complete (url change or element)
  await page.waitForTimeout(2000);
  
  // Go to post-exam
  await page.goto('http://localhost:5173/personalized/post-exam');
  
  // Wait for new button
  await page.click('button:has-text("Phân tích đề thi mới")').catch(() => {});
  await page.waitForTimeout(1000);
  
  // Wait for file input and set file
  const fileInput = await page.$('input[type="file"]');
  const filePath = path.resolve('D:\\TTTN\\personalized-learning-system\\personalized-learning-system\\test\\Test_exam.jpg');
  await fileInput.setInputFiles(filePath);
  
  // Click next (Đang xử lý tài liệu... -> Tiếp theo)
  await page.click('button:has-text("Tiếp theo")');
  
  // Wait for parsing to finish and screen to change
  console.log("Waiting for parse to finish...");
  await page.waitForTimeout(10000); // give it 10s to parse
  
  // Check if we see the score inputs
  const scoreInput = await page.$('input[placeholder="Ví dụ: 8.5"]');
  if (scoreInput) {
      await scoreInput.fill('8.5');
      console.log("Filled score");
  } else {
      console.log("No score input found");
  }
  
  // Let's check for any checkboxes
  const checkboxes = await page.$$('input[type="checkbox"]');
  if (checkboxes.length > 0) {
      await checkboxes[0].click(); // select first question
      // select radio for support level
      const radios = await page.$$('input[type="radio"]');
      if (radios.length > 0) {
          await radios[0].click();
      }
      // Click analyze
      await page.click('button:has-text("Phân tích AI")');
      
      console.log("Waiting for AI analysis to finish...");
      await page.waitForTimeout(15000); // give it 15s
      
      // Look for result
      const resultText = await page.$('text=Điểm số bài thi');
      if (resultText) {
          console.log("Result screen appeared successfully!");
      } else {
          console.log("Failed to show result screen.");
          const body = await page.innerText('body');
          console.log("Body snippet:", body.substring(0, 1000));
      }
  } else {
      console.log("No checkboxes found. Something failed during parse?");
      const body = await page.innerText('body');
      console.log("Body snippet:", body.substring(0, 1000));
  }
  
  await browser.close();
})();
