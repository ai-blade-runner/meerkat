from typing import Dict, Tuple, Union, Callable, Mapping, Sequence, TYPE_CHECKING
from inspect import getfullargspec, signature


from meerkat.block.abstract import BlockView
import meerkat.tools.docs as docs

if TYPE_CHECKING:
    from meerkat import DataFrame, Column
    from meerkat.columns.deferred.base import DeferredColumn
    from meerkat.dataframe import DataFrame


_SHARED_DOCS_ = {
    "function": docs.Arg(
        """
        function (Callable): The function that will be applied to the rows of
            ``${data}``.
        """
    ),
    "is_batched_fn": docs.Arg(
        """ 
        is_batched_fn (bool, optional): Whether the function must be applied on a
            batch of rows. Defaults to False.
        """
    ),
    "batch_size": docs.Arg(
        """
        batch_size (int, optional): The size of the batch. Defaults to 1.
        """
    ),
    "inputs": docs.Arg(
        """ 
        inputs (Dict[str, str], optional): Dictionary mapping column names in
            ``${data}`` to keyword arguments of ``function``. Ignored if ``${data}`` is a
            column. When calling ``function`` values from the columns will be fed to
            the corresponding keyword arguments. Defaults to None, in which case it
            inspects the signature of the function. It then finds the columns with the 
            same names in the DataFrame and passes the corresponding values to the 
            function. If the function takes a non-default argument that is not a 
            column in the DataFrame, the operation will raise a `ValueError`.
        """
    ),
    "outputs": docs.Arg(
        """
        outputs (Union[Dict[any, str], Tuple[str]], optional): Controls how the output 
            of ``function`` is mapped to the output of :func:`${name}`. 
            Defaults to ``None``.

            *   If ``None``: the output is inferred from the return type of the 
                function. See explanation above. 
            *   If ``"single"``: a single :class:`DeferredColumn` is returned.
            *   If a ``Dict[any, str]``: then a :class:`DataFrame` containing
                DeferredColumns is returned. This is useful when the output of
                ``function`` is a ``Dict``. ``outputs`` maps the outputs of ``function``
                to column names in the resulting :class:`DataFrame`.
            *   If a ``Tuple[str]``: then a :class:`DataFrame` containing 
                output :class:`DeferredColumn` is returned. This is useful when the 
                of ``function`` is a ``Tuple``. ``outputs`` maps the outputs of
                ``function`` to column names in the resulting :class:`DataFrame`.
        """
    ),
    "output_type": docs.Arg(
        """
        output_type (Union[Dict[str, type], type], optional): Coerce the column. Defaults
            to None.
        """
    ),
}


@docs.doc(source=_SHARED_DOCS_, data="data", name="defer")
def defer(
    data: Union["DataFrame", "Column"],
    function: Callable,
    is_batched_fn: bool = False,
    batch_size: int = 1,
    inputs: Union[Mapping[str, str], Sequence[str]] = None,
    outputs: Union[Mapping[any, str], Sequence[str]] = None,
    output_type: Union[Mapping[str, type], type] = None,
    materialize: bool = True,
) -> Union["DataFrame", "DeferredColumn"]:
    """Create one or more DeferredColumns that lazily applies a function to each row
    in ${data}.

    This function shares nearly the exact same signature
    with :func:`map`, the difference is that :func:`~meerkat.defer` returns a column
    that has not yet been computed. It is a placeholder for a column that will be
    computed later.

    Learn more in the user guide: :ref:`guide/dataframe/ops/mapping/deferred`.

    *What gets passed to function?*

    *   If ${data} is a :class:`DataFrame`, then the function's signature is
        inspected to determine which columns to pass as keyword arguments to the
        function.
        For example, if the function is
        ``lambda age, residence: age > 18 and residence == "NY"``, then
        the columns ``age`` and ``residence`` will be passed to the function. If the
        columns are not present in the DataFrame, then a `ValueError` will be raised.
        The mapping between columns and function arguments can be overridden by passing
        a the ``inputs`` argument.
    *   If ${data} is a :class:`Column` then values of the
        column are passed as a single positional argument to the function. The
        ``inputs`` argument is ignored.

    *What gets returned by defer?*

    *   If ``function`` returns a single value, then ``defer``
        will return a :class:`DeferredColumn` object.

    *   If ``function`` returns a dictionary, then ``defer`` will return a
        :class:`DataFrame` containing :class:`DeferredColumn` objects. The keys of the
        dictionary are used as column names. The ``outputs`` argument can be used to
        override the column names.

    *   If ``function`` returns a tuple, then ``defer`` will return a :class:`DataFrame`
        containing :class:`DeferredColumn` objects. The column names will be integers.
        The column names can be overriden by passing a tuple to the ``outputs`` argument.

    *   If ``function`` returns a tuple or a dictionary, then passing ``"single"`` to the
        ``outputs`` argument will cause ``defer`` to return a single :class:`DeferredColumn`
        that materializes to a :class:`ObjectColumn`.

    *How do you execute the deferred map?*

    Depending on ``function`` and the ``outputs`` argument, returns either a
    :class:`DeferredColumn` or a :class:`DataFrame`. Both are **callables**. To execute
    the deferred map, simply call the returned object.

    .. note::
        This function is also available as a method of :class:`DataFrame` and
        :class:`Column` under the name ``defer``.


    Args:
        ${data} (DataFrame): The :class:`DataFrame` or :class:`Column` to which the
            function will be applied.
        ${function}
        ${is_batched_fn}
        ${batch_size}
        ${inputs}
        ${outputs}
        ${output_type}

    Returns:
        Union[DataFrame, DeferredColumn]: A :class:`DeferredColumn` or a
            :class:`DataFrame` containing :class:`DeferredColumn` representing the
            deferred map.

    Examples
    ---------
    We start with a small DataFrame of voters with two columns: `birth_year`, which
    contains the birth year of each person, and `residence`, which contains the state in
    which each person lives.

    .. ipython:: python

        import datetime
        import meerkat as mk

        df = mk.DataFrame({
            "birth_year": [1967, 1993, 2010, 1985, 2007, 1990, 1943],
            "residence": ["MA", "LA", "NY", "NY", "MA", "MA", "LA"]
        })


    **Single input column.** Lazily create a column of birth years to a column of ages.

    .. ipython:: python

        df["age"] = df["birth_year"].defer(
            lambda x: datetime.datetime.now().year - x
        )
        df["age"]

    We can materialize the deferred map (*i.e.* run it) by calling the column.

    .. ipython:: python

        df["age"]()


    **Multiple input columns.** Lazily create a column of birth years to a column of
    ages.

    .. ipython:: python

        df["ma_eligible"] = df.defer(
            lambda age, residence: (residence == "MA") and (age >= 18)
        )
        df["ma_eligible"]()
    """
    from meerkat import DeferredColumn
    from meerkat.block.deferred_block import DeferredBlock, DeferredOp
    from meerkat.columns.abstract import Column
    from meerkat.dataframe import DataFrame

    # prepare arguments for LambdaOp
    if isinstance(data, Column):
        args = [data]
        kwargs = {}
    elif isinstance(data, DataFrame):
        if isinstance(inputs, Mapping):
            args = []
            kwargs = {kw: data[col_name] for col_name, kw in inputs.items()}
        elif isinstance(inputs, Sequence):
            args = [data[col_name] for col_name in inputs]
            kwargs = {}
        elif inputs is None:
            # infer mapping from function signature
            args = []
            kwargs = {}
            for name, param in signature(function).parameters.items():
                if name in data:
                    kwargs[name] = data[name]
                elif param.default is param.empty:
                    raise ValueError(
                        f"Non-default argument {name} does not have a corresponding "
                        f"column in the DataFrame. Please provide an `inputs` mapping "
                        f"pass a lambda function with a different signature."
                    )
        else:
            raise ValueError("`inputs` must be a mapping or sequence.")

    op = DeferredOp(
        fn=function,
        args=args,
        kwargs=kwargs,
        is_batched_fn=is_batched_fn,
        batch_size=batch_size,
        return_format=type(outputs),
    )

    block = DeferredBlock.from_block_data(data=op)

    first_row = op._get(0) if len(op) > 0 else None

    if outputs is None and isinstance(first_row, Dict):
        # support for splitting a dict into multiple columns without specifying outputs
        outputs = {output_key: output_key for output_key in first_row}
        op.return_format = type(outputs)

    if outputs is None and isinstance(first_row, Tuple):
        # support for splitting a tuple into multiple columns without specifying outputs
        outputs = tuple(map(str, range(len(first_row))))
        op.return_format = type(outputs)

    if outputs is None or outputs == "single":
        # can only infer output type if the the input columns are nonempty
        if output_type is None and first_row is not None:
            output_type = type(first_row)

        if not isinstance(output_type, type):
            raise ValueError(
                "Must provide a single `output_type` if `outputs` is None."
            )

        col = DeferredColumn(
            data=BlockView(block_index=None, block=block), output_type=output_type
        )
        return col
    elif isinstance(outputs, Mapping):
        if output_type is None:
            output_type = {
                outputs[output_key]: type(col) for output_key, col in first_row.items()
            }
        if not isinstance(output_type, Mapping):
            raise ValueError(
                "Must provide a `output_type` mapping if `outputs` is a mapping."
            )

        return DataFrame(
            {
                col: DeferredColumn(
                    data=BlockView(block_index=output_key, block=block),
                    output_type=output_type[outputs[output_key]],
                )
                for output_key, col in outputs.items()
            }
        )
    elif isinstance(outputs, Sequence):
        if output_type is None:
            output_type = [type(col) for col in first_row]
        if not isinstance(output_type, Sequence):
            raise ValueError(
                "Must provide a `output_type` sequence if `outputs` is a sequence."
            )
        return DataFrame(
            {
                col: DeferredColumn(
                    data=BlockView(block_index=output_key, block=block),
                    output_type=output_type[output_key],
                )
                for output_key, col in enumerate(outputs)
            }
        )


@docs.doc(source=_SHARED_DOCS_, data="data", name="defer")
def map(
    data: Union["DataFrame", "Column"],
    function: Callable,
    is_batched_fn: bool = False,
    batch_size: int = 1,
    inputs: Union[Mapping[str, str], Sequence[str]] = None,
    outputs: Union[Mapping[any, str], Sequence[str]] = None,
    output_type: Union[Mapping[str, type], type] = None,
    materialize: bool = True,
    pbar: bool = False,
    **kwargs,
):
    """
    Create a new :class:`Column` or :class:`DataFrame` by applying a function to each
    row in ${data}.

    This function shares nearly the exact same signature
    with :func:`defer`, the difference is that :func:`~meerkat.defer` returns a column
    that has not yet been computed. It is a placeholder for a column that will be
    computed later.

    Learn more in the user guide: :ref:`guide/dataframe/ops/mapping`.

    *What gets passed to function?*

    *   If ${data} is a :class:`DataFrame`, then the function's signature is
        inspected to determine which columns to pass as keyword arguments to the
        function.
        For example, if the function is
        ``lambda age, residence: age > 18 and residence == "NY"``, then
        the columns ``age`` and ``residence`` will be passed to the function. If the
        columns are not present in the DataFrame, then a `ValueError` will be raised.
        The mapping between columns and function arguments can be overridden by passing
        a the ``inputs`` argument.
    *   If ${data} is a :class:`Column` then values of the
        column are passed as a single positional argument to the function. The
        ``inputs`` argument is ignored.

    *What gets returned by map?*

    *   If ``function`` returns a single value, then ``map``
        will return a :class:`Column` object.

    *   If ``function`` returns a dictionary, then ``map`` will return a
        :class:`DataFrame`. The keys of the
        dictionary are used as column names. The ``outputs`` argument can be used to
        override the column names.

    *   If ``function`` returns a tuple, then ``map`` will return a :class:`DataFrame`. 
        The column names will be integers. The column names can be overriden by passing 
        a tuple to the ``outputs`` argument.

    *   If ``function`` returns a tuple or a dictionary, then passing ``"single"`` to the
        ``outputs`` argument will cause ``map`` to return a single :class:`ObjectColumn`.

    .. note::
        This function is also available as a method of :class:`DataFrame` and
        :class:`Column` under the name ``map``.


    Args:
        ${data} (DataFrame): The :class:`DataFrame` or :class:`Column` to which the
            function will be applied.
        ${function}
        ${is_batched_fn}
        ${batch_size}
        ${inputs}
        ${outputs}
        ${output_type}
        pbar (bool): Show a progress bar. Defaults to False.

    Returns:
        Union[DataFrame, DeferredColumn]: A :class:`DeferredColumn` or a
            :class:`DataFrame` containing :class:`DeferredColumn` representing the
            deferred map.

    Examples
    ---------
    We start with a small DataFrame of voters with two columns: `birth_year`, which
    contains the birth year of each person, and `residence`, which contains the state in
    which each person lives.

    .. ipython:: python

        import datetime
        import meerkat as mk

        df = mk.DataFrame({
            "birth_year": [1967, 1993, 2010, 1985, 2007, 1990, 1943],
            "residence": ["MA", "LA", "NY", "NY", "MA", "MA", "LA"]
        })


    **Single input column.** Lazily create a column of birth years to a column of ages.

    .. ipython:: python

        df["age"] = df["birth_year"].map(
            lambda x: datetime.datetime.now().year - x
        )
        df["age"]


    **Multiple input columns.** Lazily create a column of birth years to a column of
    ages.

    .. ipython:: python

        df["ma_eligible"] = df.map(
            lambda age, residence: (residence == "MA") and (age >= 18)
        )
        df["ma_eligible"]
    """

    deferred = defer(
        data=data,
        function=function,
        is_batched_fn=is_batched_fn,
        batch_size=batch_size,
        inputs=inputs,
        outputs=outputs,
        output_type=output_type,
        materialize=materialize,
    )
    return _materialize(deferred, batch_size=batch_size, pbar=pbar)


def _materialize(data: Union["DataFrame", "Column"], batch_size: int, pbar: bool):
    from .concat import concat
    from tqdm import tqdm

    result = []
    for batch_start in tqdm(range(0, len(data), batch_size), disable=not pbar):
        result.append(
            data._get(slice(batch_start, batch_start + batch_size, 1), materialize=True)
        )
    return concat(result)
