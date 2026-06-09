// Advanced test script for detecting visually grouped messages for discord
// This script is designed to run in the browser console on Discord's web app.
// It uses various methods to identify message groups based on visual proximity,
// author, and message structure. The goal is to improve the accuracy of message
// grouping detection by considering different aspects of the DOM structure.
// This script is for educational purposes and should be used responsibly.
// Please ensure you have permission to run scripts on the page and that you
// comply with Discord's terms of service.
// Note: This script may not work as intended if Discord updates its HTML structure.
// Always check for the latest structure before running the script.
function testMessageGroupingImproved() {
  console.log("Testing improved message grouping detection...");
  
  // Get all message elements - try multiple selector patterns
  const messageElements = document.querySelectorAll(
    '[id^="chat-messages-"], ' +
    '[data-list-item-id^="chat-messages-"], ' +
    '[class*="message"][role="article"], ' +
    '.messageListItem__5126c'
  );
  
  console.log(`Found ${messageElements.length} total message elements`);
  
  // Group messages by visual grouping
  const visualGroups = [];
  let currentGroup = null;
  let lastAuthor = null;
  let lastMessageId = null;
  
  // Process each message element
  for (let i = 0; i < messageElements.length; i++) {
    const msgElement = messageElements[i];
    try {
      // Get message ID from various possible attributes
      let messageId = msgElement.id || 
                      msgElement.getAttribute('data-list-item-id') || 
                      msgElement.getAttribute('id');
                      
      if (!messageId && msgElement.querySelector('[id^="message-content-"]')) {
        const contentId = msgElement.querySelector('[id^="message-content-"]').id;
        messageId = contentId.replace('message-content-', 'msg-');
      }
      
      if (!messageId) {
        console.log(`Skipping element - no ID found:`, msgElement);
        continue;
      }
      
      // Check if this is a group start message
      const isGroupStart = msgElement.classList.contains('groupStart__5126c') || 
                          msgElement.className.includes('groupStart');
      
      // Find the author - try multiple selectors
      let author = null;
      const authorElements = [
        msgElement.querySelector('.username_c19a55'),
        msgElement.querySelector('[class*="username"]'),
        msgElement.querySelector('[id^="message-username-"]')
      ].filter(el => el);
      
      if (authorElements.length > 0) {
        author = authorElements[0].textContent.trim();
      }
      
      // If we can't find an author, try to infer from group context
      if (!author && currentGroup) {
        author = currentGroup.author;
      }
      
      // Skip if we still can't determine the author
      if (!author) {
        console.log(`Skipping message ${messageId} - no author found`);
        continue;
      }
      
      // Get the message content - try multiple selectors
      let content = '';
      const contentElements = [
        msgElement.querySelector('[id^="message-content-"]'),
        msgElement.querySelector('.markup__75297'),
        msgElement.querySelector('[class*="markup"]'),
        msgElement.querySelector('[class*="messageContent"]')
      ].filter(el => el);
      
      if (contentElements.length > 0) {
        content = contentElements[0].textContent.trim();
      }
      
      // If this is a group start or different author from last message, start a new group
      if (isGroupStart || author !== lastAuthor || !currentGroup) {
        // Finish previous group if exists
        if (currentGroup) {
          visualGroups.push(currentGroup);
        }
        
        // Start new group
        currentGroup = {
          author: author,
          messages: [{
            id: messageId,
            content: content,
            element: msgElement,
            isGroupStart: isGroupStart
          }]
        };
      } else {
        // Add to current group
        currentGroup.messages.push({
          id: messageId,
          content: content,
          element: msgElement,
          isGroupStart: isGroupStart
        });
      }
      
      // Update tracking variables
      lastAuthor = author;
      lastMessageId = messageId;
    } catch (e) {
      console.error("Error processing message:", e);
    }
  }
  
  // Add the last group
  if (currentGroup) {
    visualGroups.push(currentGroup);
  }
  
  // Filter to groups with multiple messages
  const multiMessageGroups = visualGroups.filter(group => group.messages.length > 1);
  console.log(`Found ${multiMessageGroups.length} multi-message groups`);
  
  // Log detailed info about multi-message groups
  multiMessageGroups.forEach((group, index) => {
    console.log(`Group #${index + 1}: Author "${group.author}" has ${group.messages.length} messages:`);
    
    // Log each message in the group
    group.messages.forEach((msg, msgIndex) => {
      console.log(`  Message ${msgIndex + 1}: ${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''} (ID: ${msg.id})`);
      
      // Visual indicator in the UI
      try {
        msg.element.style.border = "2px solid #FF9900";
        msg.element.style.backgroundColor = "rgba(255, 153, 0, 0.1)";
        
        // Add a label
        const label = document.createElement('div');
        label.style = "position: absolute; right: 10px; top: 0; background: #FF9900; color: black; padding: 2px 5px; border-radius: 3px; font-size: 10px; z-index: 9999;";
        label.textContent = `Group ${index + 1}, Msg ${msgIndex + 1}/${group.messages.length}`;
        
        // Make sure we can position the label properly
        const position = window.getComputedStyle(msg.element).position;
        if (position === 'static') {
          msg.element.style.position = 'relative';
        }
        
        msg.element.appendChild(label);
      } catch (e) {
        console.error("Error highlighting element:", e);
      }
    });
    
    // Combined content 
    const combinedContent = group.messages.map(msg => msg.content).join('\n');
    console.log(`  Combined content would be:\n${combinedContent}`);
    console.log("----------------------------");
  });
  
  return {
    allGroups: visualGroups,
    multiMessageGroups: multiMessageGroups
  };
}

// Another approach: look for specific HTML markers in Discord's interface
function testDiscordMessageStructure() {
  console.log("Testing Discord message structure analysis...");
  
  // Look for all message containers
  const messageContainers = document.querySelectorAll(
    '[class*="message"][role="article"], ' +
    '.messageListItem__5126c, ' +
    '[data-list-item-id^="chat-messages-"]'
  );
  
  console.log(`Found ${messageContainers.length} message containers`);
  
  // Group tracking
  const groupedByUserId = new Map();
  const groupedMessagesById = new Map();
  const visualGroups = [];
  
  // Find all message content divs to analyze structure
  const contentDivs = document.querySelectorAll('[id^="message-content-"]');
  console.log(`Found ${contentDivs.length} message content divs`);
  
  // Extract message IDs from content divs
  for (const div of contentDivs) {
    const messageId = div.id.replace('message-content-', '');
    const messageContainer = div.closest('[role="article"], [data-list-item-id]');
    
    if (!messageContainer) {
      console.log(`No container found for message ${messageId}`);
      continue;
    }
    
    // Get user ID if available
    let userId = null;
    const usernameElem = messageContainer.querySelector('[id^="message-username-"]');
    if (usernameElem) {
      userId = usernameElem.id.replace('message-username-', '');
    }
    
    // Get username
    let username = null;
    const usernameContentElem = messageContainer.querySelector('.username_c19a55, [class*="username"]');
    if (usernameContentElem) {
      username = usernameContentElem.textContent.trim();
    }
    
    // Get content
    const content = div.textContent.trim();
    
    // Check if this is a grouped message (non-start)
    const isGroupStart = messageContainer.classList.contains('groupStart__5126c') || 
                         messageContainer.className.includes('groupStart');
    
    // Store data
    const messageData = {
      id: messageId,
      userId: userId,
      username: username,
      content: content,
      element: messageContainer,
      isGroupStart: isGroupStart
    };
    
    // Group by user ID if available
    if (userId) {
      if (!groupedByUserId.has(userId)) {
        groupedByUserId.set(userId, []);
      }
      groupedByUserId.get(userId).push(messageData);
    }
    
    // Store for lookup
    groupedMessagesById.set(messageId, messageData);
  }
  
  // Analyze each user's messages to identify visual groups
  groupedByUserId.forEach((messages, userId) => {
    // Sort by message ID to ensure proper order
    messages.sort((a, b) => {
      const idA = BigInt(a.id);
      const idB = BigInt(b.id);
      return idA < idB ? -1 : (idA > idB ? 1 : 0);
    });
    
    // Split into visual groups based on groupStart status
    let currentGroup = null;
    
    for (const msg of messages) {
      if (msg.isGroupStart || !currentGroup) {
        // Start a new group
        if (currentGroup) {
          visualGroups.push(currentGroup);
        }
        
        currentGroup = {
          userId: userId,
          author: msg.username,
          messages: [msg]
        };
      } else {
        // Add to current group if IDs are sequential
        const lastMsg = currentGroup.messages[currentGroup.messages.length - 1];
        const lastId = BigInt(lastMsg.id);
        const currId = BigInt(msg.id);
        
        // Check if IDs are close enough to be grouped visually
        // (Discord sometimes shows messages as grouped even if there are other messages in between)
        const idDiff = currId - lastId;
        
        // Assume they're in the same group if the difference is reasonably small
        // or if they appear visually grouped in the UI
        const isVisuallyGrouped = Math.abs(
          msg.element.getBoundingClientRect().top - 
          lastMsg.element.getBoundingClientRect().bottom
        ) < 20; // messages within a few pixels vertically
        
        if (idDiff < 1000n || isVisuallyGrouped) {
          currentGroup.messages.push(msg);
        } else {
          // Start a new group
          visualGroups.push(currentGroup);
          currentGroup = {
            userId: userId,
            author: msg.username,
            messages: [msg]
          };
        }
      }
    }
    
    // Add the last group
    if (currentGroup) {
      visualGroups.push(currentGroup);
    }
  });
  
  // Filter to multi-message groups
  const multiMessageGroups = visualGroups.filter(group => group.messages.length > 1);
  
  console.log(`Found ${multiMessageGroups.length} visual groups with multiple messages`);
  
  // Highlight and log groups
  multiMessageGroups.forEach((group, index) => {
    console.log(`Group #${index + 1}: Author "${group.author}" has ${group.messages.length} messages:`);
    
    // Process each message
    group.messages.forEach((msg, msgIndex) => {
      console.log(`  Message ${msgIndex + 1}: ${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''} (ID: ${msg.id})`);
      
      // Highlight
      try {
        msg.element.style.border = "2px solid #4CAF50";
        msg.element.style.backgroundColor = "rgba(76, 175, 80, 0.1)";
        
        // Add label
        const label = document.createElement('div');
        label.style = "position: absolute; right: 10px; top: 0; background: #4CAF50; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; z-index: 9999;";
        label.textContent = `Structure Group ${index + 1}, Msg ${msgIndex + 1}/${group.messages.length}`;
        
        // Position properly
        const position = window.getComputedStyle(msg.element).position;
        if (position === 'static') {
          msg.element.style.position = 'relative';
        }
        
        msg.element.appendChild(label);
      } catch (e) {
        console.error("Error highlighting element:", e);
      }
    });
    
    // Combined content
    const combinedContent = group.messages.map(msg => msg.content).join('\n');
    console.log(`  Combined content would be:\n${combinedContent}`);
    console.log("----------------------------");
  });
  
  return {
    allGroups: visualGroups,
    multiMessageGroups: multiMessageGroups,
    messagesByUserId: groupedByUserId,
    messagesById: groupedMessagesById
  };
}

// Third approach: detect messages by DOM proximity and structure
function testMessageProximityGrouping() {
  console.log("Testing message proximity grouping...");
  
  // Get all message elements
  const messageElements = Array.from(document.querySelectorAll(
    '[class*="message"][role="article"], ' +
    '[class*="cozyMessage"], ' +
    '[class*="message__5126c"], ' +
    '[data-list-item-id^="chat-messages-"]'
  ));
  
  console.log(`Found ${messageElements.length} message elements for proximity analysis`);
  
  // Map elements to structured data
  const messageData = messageElements.map(element => {
    // Get author
    const authorElem = element.querySelector('.username_c19a55, [class*="username"]');
    const author = authorElem ? authorElem.textContent.trim() : null;
    
    // Get content
    const contentElem = element.querySelector('[id^="message-content-"], [class*="markup"], [class*="messageContent"]');
    const content = contentElem ? contentElem.textContent.trim() : null;
    
    // Get position information
    const rect = element.getBoundingClientRect();
    
    return {
      element: element,
      author: author,
      content: content,
      top: rect.top,
      bottom: rect.bottom,
      height: rect.height,
      isGroupStart: element.classList.contains('groupStart__5126c') || element.className.includes('groupStart')
    };
  }).filter(msg => msg.author && msg.content); // Only keep messages with author and content
  
  // Sort by vertical position
  messageData.sort((a, b) => a.top - b.top);
  
  console.log(`Found ${messageData.length} messages with author and content`);
  
  // Group by proximity and author
  const proximityGroups = [];
  let currentGroup = null;
  const PROXIMITY_THRESHOLD = 40; // Pixels - adjust based on Discord's layout
  
  for (const msg of messageData) {
    // Check if this message should join the current group
    const shouldJoinGroup = currentGroup && 
                           msg.author === currentGroup.author && 
                           (msg.top - currentGroup.lastMessage.bottom) < PROXIMITY_THRESHOLD;
    
    if (shouldJoinGroup) {
      // Add to current group
      currentGroup.messages.push(msg);
      currentGroup.lastMessage = msg;
    } else {
      // Start a new group
      if (currentGroup) {
        proximityGroups.push(currentGroup);
      }
      
      currentGroup = {
        author: msg.author,
        messages: [msg],
        lastMessage: msg
      };
    }
  }
  
  // Add the last group
  if (currentGroup) {
    proximityGroups.push(currentGroup);
  }
  
  // Filter to multi-message groups
  const multiMessageGroups = proximityGroups.filter(group => group.messages.length > 1);
  
  console.log(`Found ${multiMessageGroups.length} proximity groups with multiple messages`);
  
  // Highlight and log groups
  multiMessageGroups.forEach((group, index) => {
    console.log(`Proximity Group #${index + 1}: Author "${group.author}" has ${group.messages.length} messages:`);
    
    // Process each message
    group.messages.forEach((msg, msgIndex) => {
      console.log(`  Message ${msgIndex + 1}: ${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''}`);
      
      // Highlight
      try {
        msg.element.style.border = "2px solid #9C27B0";
        msg.element.style.backgroundColor = "rgba(156, 39, 176, 0.1)";
        
        // Add label
        const label = document.createElement('div');
        label.style = "position: absolute; right: 10px; top: 0; background: #9C27B0; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; z-index: 9999;";
        label.textContent = `Proximity Group ${index + 1}, Msg ${msgIndex + 1}/${group.messages.length}`;
        
        // Position properly
        const position = window.getComputedStyle(msg.element).position;
        if (position === 'static') {
          msg.element.style.position = 'relative';
        }
        
        msg.element.appendChild(label);
      } catch (e) {
        console.error("Error highlighting element:", e);
      }
    });
    
    // Combined content
    const combinedContent = group.messages.map(msg => msg.content).join('\n');
    console.log(`  Combined content would be:\n${combinedContent}`);
    console.log("----------------------------");
  });
  
  return {
    allGroups: proximityGroups,
    multiMessageGroups: multiMessageGroups
  };
}

// Run all three test methods
console.log("\n=== IMPROVED GROUPING TEST ===");
const improvedResults = testMessageGroupingImproved();

console.log("\n=== STRUCTURE ANALYSIS TEST ===");
const structureResults = testDiscordMessageStructure();

console.log("\n=== PROXIMITY ANALYSIS TEST ===");
const proximityResults = testMessageProximityGrouping();

console.log("\n=== FINAL COMPARISON ===");
console.log(`- Improved method found ${improvedResults.multiMessageGroups.length} groups`);
console.log(`- Structure analysis found ${structureResults.multiMessageGroups.length} groups`);
console.log(`- Proximity analysis found ${proximityResults.multiMessageGroups.length} groups`);