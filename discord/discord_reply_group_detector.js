// Fixed function to extract message content without copying from replied message
// replies detector but meesages meese but replies from to whom is working good

function extractFullMessageContent(messageElement) {
  try {
    // IMPORTANT: First check if this is a reply message and make sure we don't get content from the replied message
    const isReplyMessage = messageElement.className.includes('hasReply') || 
                          !!messageElement.querySelector('[class*="repliedMessage"]');
    
    // If this is a reply, we need to be careful to only extract the actual message content
    if (isReplyMessage) {
      // Try to find the actual message content that belongs to this message, not the replied content
      // First attempt: Look for message content that is a direct child of the contents section
      const contents = messageElement.querySelector('.contents_c19a55, [class*="contents"]');
      if (contents) {
        const directContent = Array.from(contents.children)
          .filter(el => el.className.includes('markup') || el.className.includes('messageContent'))
          .map(el => el.textContent.trim())
          .join(' ');
        
        if (directContent.trim()) {
          // Check for edited status
          const isEdited = messageElement.innerHTML.includes('(edited)');
          return isEdited && !directContent.includes('(edited)') 
            ? directContent + ' (edited)'
            : directContent;
        }
      }
      
      // Second attempt: Find content by looking at the header positioning
      const headerElement = messageElement.querySelector('.header_c19a55, [class*="header"]');
      if (headerElement) {
        // Get all markup/messageContent elements that come after the header
        const contentElements = [];
        let currentElement = headerElement.nextElementSibling;
        
        while (currentElement) {
          if (currentElement.className.includes('markup') || 
              currentElement.className.includes('messageContent')) {
            contentElements.push(currentElement);
          }
          currentElement = currentElement.nextElementSibling;
        }
        
        // Combine the content from these elements
        const combinedContent = contentElements
          .map(el => el.textContent.trim())
          .join(' ');
        
        if (combinedContent.trim()) {
          // Check for edited status
          const isEdited = messageElement.innerHTML.includes('(edited)');
          return isEdited && !combinedContent.includes('(edited)') 
            ? combinedContent + ' (edited)'
            : combinedContent;
        }
      }

      // Third attempt: Try to extract only direct message content by finding content that's not in reply section
      const allContents = messageElement.querySelectorAll('[class*="content"], [class*="markup"]');
      const replyElement = messageElement.querySelector('[class*="repliedMessage"]');
      const replyContent = replyElement ? replyElement.textContent : '';
      
      // Find content elements that don't contain the reply text
      for (const el of allContents) {
        // Skip if this element is inside the reply section
        if (el.closest('[class*="repliedMessage"]')) {
          continue;
        }
        
        const content = el.textContent.trim();
        // If this content is not empty and not equal to the reply content
        if (content && content !== replyContent) {
          // Check for edited status
          const isEdited = messageElement.innerHTML.includes('(edited)');
          return isEdited && !content.includes('(edited)') 
            ? content + ' (edited)'
            : content;
        }
      }
    }
    
    // Standard content extraction for non-reply messages (same as before)
    let content = '';
    
    // STRATEGY 1: Try to get content directly from message-content ID (most reliable)
    const contentElement = messageElement.querySelector('[id^="message-content-"]');
    if (contentElement) {
      // Check if there are spans inside (Discord often splits content)
      const contentSpans = contentElement.querySelectorAll('span');
      
      if (contentSpans.length > 0) {
        // Process all spans, skipping timestamp and edit markers
        for (const span of contentSpans) {
          // Skip these specific spans
          if (span.className === 'edited_c19a55' || 
              span.className.includes('timestamp') ||
              span.className.includes('separator') ||
              span.style.display === 'none') {
            continue;
          }
          
          // Add this span's content with proper spacing
          if (span.textContent.trim()) {
            content += span.textContent + ' ';
          }
        }
      } else {
        // No spans - take the whole content
        content = contentElement.textContent.trim();
      }
      
      // Check for edited status
      const editedSpan = contentElement.querySelector('.edited_c19a55, [class*="edited"]');
      const isEdited = editedSpan || messageElement.innerHTML.includes('(edited)');
      
      // Add edited marker if it's not already included
      if (isEdited && !content.includes('(edited)')) {
        content = content.trim() + ' (edited)';
      }
      
      // If we found content, return it
      if (content.trim()) {
        return content.trim();
      }
    }
    
    // STRATEGY 2: Look for multi-line content by examining the structure
    const messageContent = messageElement.querySelector('.messageContent_c19a55, [class*="messageContent"]');
    if (messageContent) {
      // Get all text nodes and elements with content
      const textNodes = [];
      const getAllTextNodes = (element) => {
        // Skip these specific elements
        if (element.className === 'edited_c19a55' || 
            element.className.includes('timestamp') ||
            element.className.includes('separator') ||
            element.className.includes('repliedMessage') ||
            element.style.display === 'none') {
          return;
        }
        
        // Process child nodes
        for (const child of element.childNodes) {
          if (child.nodeType === 3) { // Text node
            if (child.textContent.trim()) {
              textNodes.push(child.textContent);
            }
          } else if (child.nodeType === 1) { // Element node
            getAllTextNodes(child);
          }
        }
      };
      
      getAllTextNodes(messageContent);
      content = textNodes.join(' ').trim();
      
      // Check for edited status
      const editedSpan = messageContent.querySelector('.edited_c19a55, [class*="edited"]');
      const isEdited = editedSpan || messageElement.innerHTML.includes('(edited)');
      
      // Add edited marker if it's not already included
      if (isEdited && !content.includes('(edited)')) {
        content += ' (edited)';
      }
      
      // If we found content, return it
      if (content.trim()) {
        return content.trim();
      }
    }
    
    // STRATEGY 3: Last resort - just get all text content from message element
    // First, identify sections to exclude
    const excludeSections = messageElement.querySelectorAll('[class*="replyBar"], [class*="repliedMessage"], [class*="timestamp"]');
    const excludeTexts = Array.from(excludeSections).map(el => el.textContent);
    
    // Get all text in message
    let allText = messageElement.innerText;
    
    // Remove excluded sections
    for (const excludeText of excludeTexts) {
      allText = allText.replace(excludeText, '');
    }
    
    // Clean up whitespace
    allText = allText.replace(/\s+/g, ' ').trim();
    
    // Try to find just the content part by removing names and timestamps
    const contentMatch = allText.match(/(.+?)(?:\s+—\s+\d+\/\d+\/\d+|$)/);
    if (contentMatch && contentMatch[1]) {
      allText = contentMatch[1].trim();
    }
    
    // Check for edited status
    const isEdited = messageElement.innerHTML.includes('(edited)');
    
    // Add edited marker if it's not already included
    if (isEdited && !allText.includes('(edited)')) {
      allText += ' (edited)';
    }
    
    return allText.trim();
  } catch (e) {
    console.error("Error extracting full message content:", e);
    return '';
  }
}

// Test function to verify the fix
function testReplyContentFix() {
  console.log("Testing reply content extraction fix...");
  
  // Find all message elements with replies
  const replyMessages = Array.from(document.querySelectorAll('[id^="chat-messages-"]'))
    .filter(el => el.className.includes('hasReply') || !!el.querySelector('[class*="repliedMessage"]'));
  
  console.log(`Found ${replyMessages.length} reply messages to test`);
  
  // Process each reply message
  const results = [];
  for (const msg of replyMessages) {
    try {
      // Extract original username
      const authorElement = msg.querySelector('[class*="username"]');
      const author = authorElement ? authorElement.textContent.trim() : 'Unknown';
      
      // Extract reply relationship
      const replyElement = msg.querySelector('[class*="repliedMessage"]');
      let replyTo = "Unknown";
      if (replyElement) {
        const replyUsername = replyElement.querySelector('[class*="username"]');
        if (replyUsername) {
          replyTo = replyUsername.textContent.trim().replace('@', '');
        }
      }
      
      // Extract content using the fixed function
      const content = extractFullMessageContent(msg);
      
      // Save result
      results.push({
        id: msg.id,
        author: author,
        replyTo: replyTo,
        content: content
      });
      
      // Log the result for this message
      console.log("Tested reply message:", {
        author: author,
        replyTo: replyTo,
        content: content
      });
    } catch (e) {
      console.error("Error testing message:", e);
    }
  }
  
  console.log(`Successfully tested ${results.length} reply messages`);
  console.log("Test results:", results);
  
  return results;
}

// Run the test
window.testReplyContentFix = testReplyContentFix;
console.log("Reply content fix loaded. Run window.testReplyContentFix() to test the fix.");

// Automatically run the test
setTimeout(testReplyContentFix, 1000);