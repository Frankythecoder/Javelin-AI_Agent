def max_subarray_sum(arr):
    # Initialize variables
    max_current = max_global = arr[0]
    
    for i in range(1, len(arr)):
        # Calculate the maximum subarray sum ending at index 'i'
        max_current = max(arr[i], max_current + arr[i])
        
        # Update the global max if the current max is greater
        if max_current > max_global:
            max_global = max_current
            
    return max_global

if __name__ == "__main__":
    array = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
    print("Maximum subarray sum is:", max_subarray_sum(array))