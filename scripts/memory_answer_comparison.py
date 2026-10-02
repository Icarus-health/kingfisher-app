"""Exact request comparison for the isolated M3 diagnostic (not production)."""
import copy


def differing_paths(left, right, path='$'):
    """Report changed paths, keeping source contents out of error summaries."""
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        return [p for key in sorted(left.keys() | right.keys()) for p in
                ([path+'.'+key] if key not in left or key not in right else
                 differing_paths(left[key],right[key],path+'.'+key))]
    if isinstance(left, list):
        if len(left)!=len(right):
            return [path+'.length']
        return [p for i,(a,b) in enumerate(zip(left,right)) for p in differing_paths(a,b,f'{path}[{i}]')]
    return [] if left==right else [path]


def compare_requests(before, after, before_prompt, after_prompt):
    """Only remove the exact first system prefix; retain every other wire field."""
    normalized=[]
    for label,requests,prompt in [('before',before,before_prompt),('after',after,after_prompt)]:
        if len(requests)!=1 or not isinstance(prompt,str) or not prompt:
            return [label+'.request_count_or_prompt']
        request=copy.deepcopy(requests[0])
        messages=request.get('messages')
        if not isinstance(messages,list) or not messages or not isinstance(messages[0],dict):
            return [label+'.messages[0]']
        first=messages[0]
        content=first.get('content')
        if first.get('role')!='system' or not isinstance(content,str) or not content.startswith(prompt) or content.count(prompt)!=1:
            return [label+'.messages[0].system_prefix']
        first['content']='<APPROVED_SYSTEM_PROMPT>'+content[len(prompt):]
        normalized.append(request)
    return differing_paths(*normalized)
