# # class ListNode:
# #     def __init__(self,val=0,next=None):
# #         self.val=val
# #         self.next=next
# #
# # def is_reverse(head:ListNode|None)->ListNode|None:
# #     previous=None
# #     current=head
# #     while current is not None:
# #         next_node=current.next
# #         current.next=previous
# #         previous=current
# #         current=next_node
# #     return previous
# #
# # def is_build(nums):
# #     dummy=ListNode()
# #     current=dummy
# #     for val in nums:
# #         current.next=ListNode(val)
# #         current=current.next
# #     return dummy.next
# #
# # def is_nums(head:ListNode):
# #     values=[]
# #     current=head
# #     while current is not None:
# #         values.append(current.val)
# #         current=current.next
# #     return values
# # if __name__=="__main__":
# #     cases=[
# #         ([1,2,3,4,5],[5,4,3,2,1]),
# #         ([1,2],[2,1]),
# #         ([],[]),
# #         ([1],[1]),
# #     ]
# #     for num,want in cases:
# #         head=is_build(num)
# #         previous=is_reverse(head)
# #         got=is_nums(previous)
# #         print(num,got,"ok"if want==got else"wrong")
#
# # class ListNode:
# #     def __init__(self,val=0,next=None):
# #         self.val=val
# #         self.next=next
# # def is_sum(head1:ListNode,head2:ListNode)->ListNode:
# #     dummy=ListNode()
# #     current=dummy
# #     temp1=head1
# #     temp2=head2
# #     while temp1 is not None and temp2 is not None:
# #         if temp1.val>=temp2.val:
# #             current.next=temp2
# #             current=current.next
# #             temp2=temp2.next
# #         else:
# #             current.next=temp1
# #             current=current.next
# #             temp1=temp1.next
# #     if temp1:
# #         current.next=temp1
# #     if temp2:
# #         current.next=temp2
# #     return dummy.next
# # def is_listnode(num)->ListNode:
# #     dummy=ListNode()
# #     current=dummy
# #     for val in num:
# #         current.next=ListNode(val)
# #         current=current.next
# #     return dummy.next
# #
# # def is_num(head:ListNode):
# #     num=[]
# #     current=head
# #     while current is not None:
# #         num.append(current.val)
# #         current=current.next
# #     return num
# #
# # if __name__=="__main__":
# #     cases=[
# #         ([1,2,4],[1,3,4],[1,1,2,3,4,4]),
# #     ]
# #     for num1,num2,want in cases:
# #         head1=is_listnode(num1)
# #         head2=is_listnode(num2)
# #         head=is_sum(head1,head2)
# #         got=is_num(head)
# #         print(num1,num2,got,"ok" if got==want else "wrong")
#
# # def is_merge(intervals:list[list[int]])->list[list[int]]:
# #     if not intervals:
# #         return []
# #     intervals.sort(key=lambda intervals:intervals[0])
# #     merged=[intervals[0]]
# #     for current_start,current_end in intervals[1:]:
# #         last_start,last_end=merged[-1]
# #         if current_start<=last_end:
# #             merged[-1][1]=max(current_end,last_end)
# #         else:
# #             merged.append([current_start,current_end])
# #     return merged
# #
# # if __name__=="__main__":
# #     print(is_merge([[1, 3], [2, 6], [8, 10], [15, 18]]))
#
# # def is_land(island:list[list[str]])->int:
# #     rows=len(island)
# #     cols=len(island[0])
# #     count=0
# #     areas=[]
# #     def dfs(row:int,col:int):
# #         if row < 0 or row >= rows:
# #             return 0
# #
# #         if col < 0 or col >= cols:
# #             return 0
# #
# #         if island[row][col]=="0":
# #             return 0
# #         island[row][col] ="0"
# #
# #         return dfs(row+1,col)+dfs(row-1,col)+dfs(row,col+1)+dfs(row,col-1)+1
# #
# #     for row in range(rows):
# #         for col in range(cols):
# #             if island[row][col]=="1":
# #                 areas.append(dfs(row,col))
# #     areas.sort()
# #     return areas[-1]
# #
# # if __name__=="__main__":
# #     text=[["1","1","0","0","0"],["1","1","0","0","0"],["0","0","1","0","0"],["0","0","0","1","1"]]
# #     print(is_land(text))
#
# # def length_of_longest(s: str) -> int:
# #     window = set()          # 当前窗口里的字符集合
# #     left = 0
# #     best = 0
# #     for right in range(len(s)):
# #         while s[right] in window:   # 新字符和窗口里撞了，先从左边往外赶
# #             window.remove(s[left])
# #             left += 1
# #         window.add(s[right])        # 赶干净了，新字符入窗
# #         best = max(best, right - left + 1)
# #     return best
# #
# #
# # if __name__=="__main__":
# # if __name__=="__main__":
#
# #     test="pwwkew"
# #     print(length_of_longest(test))
#
# #     print(length_of_longest(test))
#
#
# # class ListNode:
# #     def __init__(self,val=0,next=None):
# #         self.val=val
# #         self.next=next
# # def is_node(num:list[int])->ListNode:
# #    dummy=ListNode()
# #    current=dummy
# #    for val in num:
# #        current.next=ListNode(val)
# #        current=current.next
# #    return dummy.next
# #
# # def is_array(head:ListNode)->list[int]:
# #     num=[]
# #     while head is not None:
# #         num.append(head.val)
# #         head=head.next
# #     return num
# #
# # def is_sum(s1:ListNode,s2:ListNode)->ListNode:
# #     sum1=sum2=total=0
# #     base1=1
# #     while s1 is not None:
# #         sum1=sum1+s1.val*base1
# #         base1=base1*10
# #         s1=s1.next
# #     base2=1
# #     while s2 is not None:
# #         sum2=sum2+s2.val*base2
# #         base2=base2*10
# #         s2=s2.next
# #     total=sum2+sum1
# #     array=[int(ch) for ch in str(total)[::-1]]
# #     return is_node(array)
# #
# #
# # if __name__=="__main__":
# #     test=[([2,4,3],[5,6,4])]
# #     for num1,num2 in test:
# #         s1=is_node(num1)
# #         s2=is_node(num2)
# #         s3=is_sum(s1,s2)
# #         result=is_array(s3)
# #         print(result)
#
# # class Query:
# #     def __init__(self):
# #         self.in_stack = []  # 入队栈：自己造一个空列表挂上
# #         self.out_stack = []  # 出队栈：同上
# #
# #     def push(self, x):
# #         self.in_stack.append(x)
# #
# #     def pop(self):
# #         if not self.out_stack:
# #             while self.in_stack:
# #                 self.out_stack.append(self.in_stack.pop())
# #         return self.out_stack.pop()
# #
# #
# #
# # if __name__ == "__main__":
# #     q1 = Query()
# #     q1.push(3)
# #     q1.push(5)
# #     print(q1.pop())
#
# # def is_luoxuan(num:list[list[int]])->list[int]:
# #     hangs=len(num[0])
# #     lies=len(num)
# #     result=[]
# #     def is_right(hang:int,lie:int):
# #         if hang>=hangs:
# #             return
# # class Node:
# #     def __init__(self,val=0,key=0):
# #         self.val=val
# #         self.key=key
# #         self.previous=None
# #         self.next=None
# # class SListNode:
# #     def __init__(self):
# #         self.head=Node()
# #         self.tail=Node()
# #         self.head.next=self.tail
# #         self.tail.previous=self.head
# #
# #     def add_to_head(self,node:Node):
# #         first=self.head.next
# #         node.previous=self.head
# #         node.next=first
# #         self.head.next=node
# #         first.previous=node
# #
# #     def remove(self,node:Node):
# #         ahead=node.previous
# #         after=node.next
# #         ahead.next=after
# #         after.previous=ahead
# #
# #     def remove_tail(self):
# #         target=self.tail.previous
# #         ahead=target.previous
# #         ahead.next=self.tail
# #         self.tail.previous=ahead
# #         return target
# # class LRUCache:
# #     def __init__(self,capacity):
# #         self.cache={}
# #         self.list=SListNode()
# #         self.capacity=capacity
# #     def get(self,key):
# #         if key not in self.cache:
# #             return -1
# #         node=self.cache[key]
# #         self.list.remove(node)
# #         self.list.add_to_head(node)
# #         return node.val
# #     def put(self,key,value):
# #         if key in self.cache:
# #             node=self.cache[key]
# #             node.val=value
# #             self.list.remove(node)
# #             self.list.add_to_head(node)
# #             return
# #         node=Node(key,value)
# #         self.cache[key]=node
# #         self.list.add_to_head(node)
# #         if len(self.cache) > self.capacity:
# #             old_node = self.list.remove_tail()
# #
# #             # 从字典中删除被淘汰节点
# #             del self.cache[old_node.key]
# #
# # #eaeba
# # def is_len(s:str):
# #     count={}
# #     left=0
# #     for right in range(len(s)):
# #         count[s[right]]=count.get(count[s[right]],0)+1
# #         while len(count)>2:
# #             count[s[left]]-=1
# #             if count[s[left]]==0:
# #                 del count[s[left]]
# #             left+=1
# #         best=max(right+left-1,best)
# #     return best
# #
# # #[[1,3],[2,6],[8,10],[15,18]]   [1,6]
# # def is_merge(l:list[list[int]])->list[list[int]]:
# #     result=[]
# #     l.sort(key=lambda l:l[0])
# #     current=0
# #     result.append(l[0])
# #     for right in range(1,len(l)):
# #         if l[right][0]<=result[current][1]:
# #             result[current][1]=max(result[current][1],l[right][1])
# #         if l[right][0]>result[current][1]:
# #             result.append([l[right][0],l[right][1]])
# #             current+=1
# #     return result
# # #babad → bab 或 aba 都算对，cbbd → bb。
# #
# #
# # def is_max(s:str)->str:
# #     count=0
# #     left=0
# #     def expand(left:int,right:int):
# #         while left>=0 and right<len(s) and s[left]==s[right]:
# #             left-=1
# #             right+=1
# #         return s[left+1:right]
# #     best=""
# #     for i in range(len(s)):
# #         jishu=expand(i,i)
# #         oushu=expand(i,i+1)
# #         if len(jishu)>=len(best):
# #             best=jishu
# #         if len(oushu)>=len(best):
# #             best=oushu
# #     return best
# # #换。无重复字符的最长子串——今晚刚研读过滑窗的计数版，
# # # 这道是 set 版，骨架一样：abcabcbb → 3，pwwkew → 3
# # def is_maximum(s:str)->int:
# #     count=set()
# #     left=0
# #     best_lenth=0
# #     for right in range(len(s)):
# #         while s[right] in count:
# #             count.remove(s[left])
# #             left+=1
# #         count.add(s[right])
# #         best_lenth=max(best_lenth,right-left+1)
# #     return best_lenth
# #
# # class ListNode:
# #     def __init__(self,val=0,next=None):
# #         self.val=val
# #         self.next=next
# #
# # def is_mergee(node1:ListNode,node2:ListNode)->ListNode:
# #     base1=1
# #     result1=0
# #     current1=node1
# #     while current1 is not None:
# #         result1=result1+current1.val*base1
# #         base1=base1*10
# #         current1=current1.next
# #     base2 = 1
# #     result2 = 0
# #     current2 = node2
# #     while current2 is not None:
# #         result2 = result2 + current2.val * base2
# #         base2 = base2 * 10
# #         current2 = current2.next
# #     target=str(result1+result2)
# #     reverse_target=target[::-1]
# #     dummy=ListNode()
# #     current=dummy
# #     for ch in reverse_target:
# #         current.next=ListNode(ch)
# #         current=current.next
# #     return dummy.next
# #
# #
# # def is_merge(l:list[list[int]])->list[list[int]]:
# #     count=[]
# #     current=0
# #     l.sort(key=lambda l:l[0])
# #     count.append(l[0])
# #     for right in range(1,len(l)):
# #         if l[right][0]<=count[current][1]:
# #             count[current][1]=max(count[current][1],l[right][1])
# #         if l[right][0]>count[current][1]:
# #             count.append(l[right])
# #             current+=1
# #     return count
# # print(is_merge([[1,3],[2,6],[8,10],[15,18]]))
#
#
# class ListNode:
#     def __init__(self,val=0,next=None):
#         self.val=val
#         self.next=next
#
# # def is_reverse(l:ListNode)->ListNode:
# #     previous=None
# #     current=l
# #     while current is not None:
# #         next_node=current.next
# #         current.next=previous
# #         previous=current
# #         current=next_node
# #     return current.next
