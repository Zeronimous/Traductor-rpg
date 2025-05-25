import math

def print_neatly_optimizer(words, n, M):
    """
    Function prints a paragraph neatly
    @param words : an array of words
    @param n : number of words in the array
    @param M : maximum line length
    """
    minpenalty = [float('inf')]*(n+1)
    break_points = [None]*(n+1)

    # initialize base case
    minpenalty[0] = 0

    def compute_line_cost(extra_space, j, n_total_words):
        if extra_space < 0:
            return float('inf')
        elif j == n_total_words and extra_space >= 0:
            return 0
        else:
            return extra_space**3

    for j_word_idx in range(1, n+1):
        for i_word_idx in range(1, j_word_idx + 1):
            current_line_words = words[i_word_idx : j_word_idx+1]
            line_len = len(' '.join(current_line_words))
            
            cost = compute_line_cost(M - line_len, j_word_idx, n)

            if minpenalty[i_word_idx-1] != float('inf') and \
               (minpenalty[j_word_idx] > (minpenalty[i_word_idx-1] + cost)):
                minpenalty[j_word_idx] = minpenalty[i_word_idx-1] + cost
                break_points[j_word_idx] = i_word_idx

    return minpenalty, break_points


def reconstruct_lines(words, j_idx, break_points):
    i_idx = break_points[j_idx]
    neat_text = []
    if i_idx is None or i_idx == 0: # Modified None check, and 0 for base
        return []
        
    if i_idx > 1:
        neat_text = reconstruct_lines(words, i_idx - 1, break_points)
    
    current_line_segment = words[i_idx : j_idx+1]
    neat_text.append(' '.join(current_line_segment))
    return neat_text


def print_neatly(text, M):
    if not text:
        return []
    
    words_arr = text.split(' ')
    n = len(words_arr)
    
    if n == 0: # Added check for empty list after split (e.g. if text was just spaces)
        return []

    words_1_indexed = ['BLANK'] + words_arr 
    
    min_penalties, p_list = print_neatly_optimizer(words_1_indexed, n, M)
    
    if min_penalties[n] == float('inf'):
        if len(words_arr) == 1 and len(words_arr[0]) > M:
            return [words_arr[0][k:k+M] for k in range(0, len(words_arr[0]), M)]
        # Fallback for cases where no solution is found by optimizer
        # This might happen if p_list[n] is None or 0 without a proper path
        # A simple fallback is to just return the text as is, or split by M if too long
        current_line = ""
        result = []
        for word in words_arr:
            if not current_line:
                current_line = word
            elif len(current_line) + 1 + len(word) <= M:
                current_line += " " + word
            else:
                result.append(current_line)
                current_line = word
        if current_line:
            result.append(current_line)
        return result

    neat_text = reconstruct_lines(words_1_indexed, n, p_list)
    return neat_text
