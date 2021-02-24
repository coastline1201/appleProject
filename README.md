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
