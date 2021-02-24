# appleProject
 
This a web application for planning order executions, build using Flask framework.

Inputs are: 
* a demand order csv file containing customer, product, order date and requiring quantity; 
* a supply csv file containing supply site, product, predicted supply date and quantity; 
* a sourcing rule csv file representing which customer product can source from which site, contaning site customer and product.

Output is an allocation plan representing order fullfilment each day for each order, each record contains site, customer, product and fullfiled amount for each calendar day.

Details:
### UI
An interactive UI provides the following functionalities:
1. upload/download/replace input files
2. view allocation plan and download a csv version of it
3. display detailed input file errors (explained in Input validation section)
4. clear all input files and allocation result

### Allocation logic
Rules:
1. The basic allocation logic: Sort all the orders table by date in ascending order. For each one of them, check sourcing rule table to find the site this customer-product combination can source from. And then check the supply table for that site-product combination and exhaust all the available supply. Since orders should be processed in a first-come-first-serve manner, it’s ok that an earlier order greedily takes all it needs and leaves none for orders that comes in later. In the result table, each row is a unique site-customer-product combination, if there is fulfillment yield from the above look up procedure on a day, mark the fulfilled quantity in that date’s column, otherwise leave the date’s column empty. 
2. The final allocation result does not necessarily fulfill all the orders completely,  because of lack of supply, some orders are fully fulfilled, some are partially fulfilled, and some are not fulfilled at all (which will be omitted from the result table). The result does not need to use up all the supply either, because of not enough demands.
3. Allocation rule for orders that come on the same day: if the orders do not result in a supply competition, e.g. different product or different sourcing site, then it should not matter which order is executed first, should be executed in a way as if they were executed sequentially; If the order do require the same product from the same set of sites, and if there are enough quantity for all the orders, fulfill them all, leave the left over supply for future use; if the supply quantity is less than all the demands combined, then orders will be fulfilled proportionally based on each customer's original demand, e.g. C001 demands 5000 and C002 demands 1000 for the same product from the same site on the same day, and there are only 600 supply quantity available, then C001 should get 500 and C002 should get 100 on that day; for later fullfilments, even though the actually demand for C001 becomes 4500, and actual demand for C002 becomes 900, the portion of one customer can get from supplies should still be calculated based on their original demands, which is 5000:1000. 
4. In order to completely split the supply between same day orders and avoid supply undivisible problem, the last order on that day may get a few more supplies than what is calculted proportionally.

Assumptions:
1. It is possible that customers source same product from different site? Like for P002, C001 sources from 1206 but C002 sources from 1207.
2. There’s no up limit on how many quantity of different products can be fulfilled on one day. That means if there are enough supply, all the orders can be filled in one day.
3. There is unlimited storage space for supplies. Supplies that are not used up on previous days can be used on later days.
4. The current date should not matter in the calculation. The order date can be earlier or later than current date, so as the projected supply date. Though I suppose the most common case is order date is earlier than current date and projected supply date is later than current date, other cases can also be valid.
### Input validation
The following validation for uploaded csv files are done before proceed to allocation. All the catched errors will be shown on the UI after upload.
1. check file is not empty
2. check required columns for each type of file are included
3. check that all rows in one file have the same number of columns
4. for quantity column, check it is a valid base10 number
5. for date column, check it is in one of the 3 formats: %d-%b-%y, %d/%m/%y, %Y-%m-%d. Though ISO date format (%Y-%m-%d) is recommended since it is least ambiguous. Dates in output file are in ISO format.
Note: for easy of use, files may contain more columns than what is required, as long as all the required ones are included. Columns can also be in arbitrary order.
### Tests
Unit tests for allocation logic, covers the following scenarios:
1. a scequence of orders on different days, total supply is more than total demand -- orders should be executed scequentially based on order dates, all the orders can be fullfilled.
2. a scequence of orders on different days, total supply is less than total demand -- orders should be executed scequentially based on order dates, orders are partially fullfilled, even when using up all the supply.
3. unbalanced sourcing site, 2 customers ordering the same product, but one can source from more supply sites than the other -- orders are executed scequentially, the customer has more sourcing sites may have more entries in the results than the other.
4. multiple orders from multiple customers and for multiple products on the same day, followed by another batch of multiple orders on a later date -- all the orders on the same day should be procceed together, orders for the same product will be allocated supplies based on rules described in Allocation logic section; orders requiring different products should not interfere each other, and should be as if they were executed sequentially. After the first batch finishes, the second batch of orders can only use the supplies that were left by the first batch.
5. orders for same product from different customers with unlabanced sourcing sites on the same day. Tested different scenario combinations where 1) customer has fewer sourcing sites has more or less demand than other customers; 2) site providing for more customers are sorted to go before or after other sites during execution -- all the scenario should follow the said allocation rule and unbalanced site behavior.  
6. empty test cases: order file, supply file or sourcing file is empty respectively -- should return an empty result.
