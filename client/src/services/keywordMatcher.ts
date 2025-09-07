/**
 * Utility functions for keyword matching and highlighting in text
 */

export interface KeywordMatch {
  text: string;
  isKeyword: boolean;
  originalKeyword?: string;
}

/**
 * Matches keywords in text and returns an array of text parts with match information
 * @param keywords - Array of keywords to match
 * @param text - Text to search for keywords
 * @returns Array of KeywordMatch objects representing text parts
 */
export function matchKeywords(keywords: string[], text: string): KeywordMatch[] {
  if (!keywords.length || !text) {
    return [{ text, isKeyword: false }];
  }

  // Create a regex pattern for all keywords (case insensitive)
  const keywordPattern = keywords
    .map(keyword => keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) // Escape special regex characters
    .join('|');
  
  if (!keywordPattern) {
    return [{ text, isKeyword: false }];
  }

  const regex = new RegExp(`\\b(${keywordPattern})\\b`, 'gi');
  
  // Split text by keywords while keeping the keywords
  const parts = text.split(regex);
  
  return parts
    .filter(part => part.length > 0) // Remove empty strings
    .map(part => {
      const matchingKeyword = keywords.find(keyword => 
        keyword.toLowerCase() === part.toLowerCase()
      );
      
      return {
        text: part,
        isKeyword: !!matchingKeyword,
        originalKeyword: matchingKeyword
      };
    });
}
