# Plantilla Trabajo Fin de Estudios de la Escuela Politécnica de Cáceres #

Esta plantilla tiene como objetivo facilitar la redacción del Trabajo Fin de Estudios para aquellos estudiantes que quieran realizarlo en LaTeX.


## Estructura de la plantilla ##

La plantilla se divide en diferentes partes:

- main.tex: este es el fichero principal, y el que se ejecuta cuando se genera el documento pdf al compilar. Incluye todas las dependencias necesarias y se encarga de importar el contenido de cada capítulo. Por defecto se incluyen los capítulos de la normativa, aunque pueden ser cambiados por criterio tanto del autor como de los tutores. 

Al principio del documento se pueden incluir los paquetes que se vayan a usar adicionales a los que ya se encuentran, recomendando al menos dos: babel (para ponerlo en español, si se comenta o quita se traducen los nombres de los capítulos estándar y las referencias internas directamente al inglés) y parskip (para cambiar las sangrías por espaciado entre párrafos).
 
Los estudiantes deben rellenar el documento con sus datos a través de los comandos \title y \estudiante respectivamente, aportando al primero el título del trabajo y al segundo el nombre completo, tipo de estudios (grado o máster) y titulación del autor. También se incluye una opción para establecer las keywords del documento con el comando \keywords, para poner las palabras o temáticas más destacables del trabajo separadas por el comando \and. 
    
Para la portada hace falta añadir la convocatoria y año para que se muestre, y para la contraportada es obligatorio añadir el nombre completo del tutor con el parámetro tutor, siendo opcional especificar un cotutor y el género de cualquiera de los tres nombres mostrados para cambiar el título adjunto (por ejemplo, poner en los parámetros studentGender = f hace que se muestre Autora).
    
También se tiene que hacer un resumen del trabajo antes de los índices, mostrando las palabras clave definidas anteriormente, y se puede hacer una traducción en inglés (siendo obligatorio añadirla en trabajos de Fin de Máster para Ingenierías de Telecomunicación e Informática respectivamente). Opcionalmente, se puede añadir un capítulo antes del resumen para poner las dedicatorias.

- tfeEPCC.cls: esta es la clase que define el tipo de documento para el trabajo, y provee las funciones para generar la portada y la contraportada, así como los paquetes fundamentales y modificaciones para su correcto funcionamiento. No se recomienda modificarlo directamente, sino realizar las adaptaciones necesarias en el preámbulo o en un fichero .sty antes del comando \begin{document}.

- chapters: este directorio contiene los capítulos separados en ficheros para organizar su edición. En caso de que se vaya a modificar la estructura de capítulos, se recomienda adaptar los nombres de los ficheros empleados y cambiar los \import correspondientes en el fichero main.tex.

- appendices: este directorio es parecido a chapters, pero separando el contenido de los anexos. Si se van a importar al documento, es muy importante usar antes el comando \startappendices para comenzar con los anexos, con una página que los separa del resto del documento.

- pictures: este directorio es para colocar las imágenes que se vayan a mostrar, incluyendo de base los logos para la portada y contraportada. Se recomienda crear una carpeta interna por capítulo para poner las imágenes correspondientes dentro y organizarlas mejor.

- code: este directorio es para colocar los ficheros de código que se quieran mostrar con el comando \inputminted, pudiendo seguir las mismas medidas que con la carpeta antes descrita.

- LocalBibliography.bib: este fichero es para incluir las referencias bibliográficas del trabajo en formato bibtex, se pueden usar los siguientes enlaces para obtener más información:

https://www.bibtex.com/s/bibliography-style-urlbst-alphaurl/
https://www.bibtex.com/s/bibliography-style-urlbst-unsrturl/
https://www.bibtex.com/g/bibtex-format/

Para todas las entradas que se vayan a incluir, se recomienda si es posible incluir un enlace con el campo url, y en el caso de artículos un DOI a través del campo doi, para facilitar su acceso en caso de querer consultar.

- .github y .gitignore: este directorio y fichero sirven en caso de querer compilar el proyecto usando GitHub Actions, explicándose su uso más adelante en el apartado ## Herramientas para compilar ##.


## Opciones de la plantilla ##
Cuando se declara el tipo de documento con el comando \documentclass al principio del fichero main.tex se pueden especificar tres opciones entre [], que alteran propiedades de la plantilla por defecto:

- minitoc: al especificar esta opción, se incluirá un índice al principio de cada capítulo con sus secciones y subsecciones correspondientes, para facilitar su visualización y acceso además del índice al principio del documento.

- hidelinks: por defecto, los enlaces del documento están rodeados de un borde rectangular, con un color dependiendo de si es una referencia interna, una cita bibliográfica o un vínculo externo. Especificando esta opción, se ocultan estos bordes para facilitar la lectura, y se colorea de color azul el texto de los vínculos externos para distinguirlos del resto.

- headlogo: especificando esta opción, se incluye a la derecha del encabezado entre capítulos el logo de la Universidad.

- framedcover: especificando esta opción, se añade un recuadro a la portada y contraportada de la plantilla.


## Herramientas para compilar ##
A continuación se incluyen algunas de las herramientas que pueden usarse para generar el documento:

- Overleaf: esta puede ser la opción más cómoda de primeras, ya que no requiere instalar nada para usarse y basta con tener una cuenta para importar el documento y compilarlo, guardándose en la nube y centralizando el acceso para diferentes ordenadores. Sin embargo, en caso de que su extensión supere cierto tamaño, es posible que deje de compilar con una cuenta gratuita, por lo que puede que haga falta usar otra de las opciones recomendadas a continuación.
 
- GitHub: esta es otra buena herramienta para guardar el estado del documento en la nube, pudiendo guardar el proyecto en un repositorio privado y hacer uso de GitHub Actions como por ejemplo el que se ofrece en el ejemplo de este repositorio(https://github.com/xu-cheng/latex-action), especificando los pasos en un fichero .yml dentro del directorio especial .github/workflows para que se ejecuten tras cada commit push, y pudiendo incluir un fichero .gitignore como el de este repositorio(https://github.com/merkez/latex-on-ci-cd) en caso de que se vaya a combinar su uso con el próximo método explicado.

Para facilitar este proceso, se proveen también con la plantilla una versión funcional de estos ficheros para generar el documento base en caso de optar por esta opción, siendo necesario modificar el nombre que se le va a dar al documento generado en el fichero .github/workflows/compileandrelease.yml. Por defecto está puesto TFX_AAABBCCCC_20DD.pdf, cambiando la X por G para Grado y M para Máster, AAA son las siglas de la titulación, BB son las siglas de la especialidad si es que el título tiene, CCCC es el número de expediente, que se puede ver en el Portal Servicios(https://portal.unex.es/ServiciosApp/), y DD es el año de realización.

Para subir los ficheros al repositorio, después de crearlo poniendo datos como su nombre y si se va a hacer público o privado (siendo preferible esta última opción) aparece una opción de gestión rápida, con la posibilidad de subir directamente los ficheros de la plantilla al repositorio tras descomprimirla. Otra forma de subir los ficheros es usando la herramienta GitHub Desktop, seleccionando el repositorio correspondiente para clonarlo en una carpeta sincronizada en el ordenador, y guardando los cambios en un commit cuando se hayan introducido todos los ficheros en ella para finalmente seleccionar la opción de publicar la rama a GitHub.

Si bien se recomienda editar y guardar los cambios en el repositorio desde un editor de código, también es posible hacer uso de GitHub Dev(https://github.com/github/dev), con el que pulsando la tecla . desde el repositorio o cambiando en el enlace de GitHub .com por .dev se puede abrir una versión web del editor Visual Studio Code para modificar directamente el código, dando la opción para guardar los cambios como un commit.

Cabe destacar que, si bien GitHub tiene límites de almacenamiento de 500mb para artefactos asociados a commits y 2000 minutos de ejecución al mes de GitHub Actions por defecto, se puede solicitar acceso educacional(https://education.github.com/pack) con la matrícula de la universidad para hacer más leves estas restricciones.
    
- Compilación local: este método requiere instalar LaTeX y todas las dependencias del documento en el ordenador donde se vaya a realizar, si bien como se ha mencionado antes es posible usar un repositorio para guardar los cambios en la nube.

Se pueden usar instalaciones de LaTeX como MiKTeX(https://miktex.org/) o TeX Live(https://tug.org/texlive/), necesitando algunas dependencias como la librería perl(https://www.perl.org/get.html). Junto a estas instalaciones se puede hacer uso de editores de código para facilitar la ejecución y añadir facilidades de manejo del repositorio, como Visual Studio Code(https://code.visualstudio.com/), que incluye extensiones como LaTeX Workshop(https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) para simplificar enormemente la edición y visualización del documento.

Para cada paquete que se vaya a instalar se recomienda leer su documentación asociada en el CTAN(https://ctan.org/), ya que algunos paquetes necesitan ajustes adicionales para funcionar. Por ejemplo, minted requiere cargar python y el ejecutable latexminted en el PATH para formatear código, y necesita añadir también la opción -shell-escape a los argumentos en las opciones de compilación en LaTeX (en Visual Studio Code se puede hacer pulsando las teclas Control + Shift + P, eligiendo la opción Preferences: Open Settings (UI), buscando con la barra de búsqueda "latex tools" y seleccionando Edit in settings.json, y por último añadiendo el parámetro "-shell-escape" con una coma al final dentro del apartado args del comando que se vaya a usar para la compilación, siendo latexmk por defecto, guardando este ajuste pulsando las teclas Control + S o pulsando la opción File - Save).