First of all, love this question haha, is so hard to even get an interview this days, that 
just being able to do a small "quiz" feels nice. 

My approach here was: 
 a) generate the schemas for the set of googlesuper tools using my agent
 b) create a generalizable pipeline with LLMs so they diges the incoming group of tools
    and make the relationship schema useful in a general manner. That way, I hope to not have
    to create new set of rules for any new incoming set of tools index. 
  c) compare my "manual" approach to the LLM-guided approach.
  d) once it works, just rerun my approach to github.
  
Even though this may take longer initially, the effort needed to iterate later on newer and more complex
tools is reduced. So maybe for this test that i had to do only 2 graphs was unnecesary, but that way I ended up with something reusable.
In the end, you gotta be a sucker for automation, when you want to build agents as a job 

First iteration of the LLM processing was very slow, so decided to parallelize to make it faster.
I could definitely make it faster by prefiltering by "standard" tool schemas, and only using the LLM when needed. 

Hahah! ran out of time when i was almost done!, oh well, the pipeline works :) so I'll finish it "manually"/"deterministically" and submit.

This are ideas to make the graph nicer (given extra time):
- Make a reachability tool that can tell from a starting point in the graph if another point is reachable
    - Basically checking if there is a path between to nodes in the graph

- Untangle relationships (although i can tune the confidence, there has to be a nice graph algorithm to help with this, although i 
would be surprised if inside networkx this is not happening already)

