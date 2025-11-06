# Use newer Python version with updated compilers
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY generate_report.py ${LAMBDA_TASK_ROOT}

# Set the Lambda handler
CMD ["generate_report.lambda_handler"]